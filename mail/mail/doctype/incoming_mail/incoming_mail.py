# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from uuid_utils import uuid7
from typing import TYPE_CHECKING
from email.utils import parseaddr
from frappe.model.document import Document
from mail.utils.cache import get_postmaster
from mail.rabbitmq import rabbitmq_context
from mail.utils.email_parser import EmailParser, extract_ip_and_host
from mail.mail.doctype.mail_contact.mail_contact import create_mail_contact
from mail.mail.doctype.outgoing_mail.outgoing_mail import create_outgoing_mail
from frappe.utils import now, cint, time_diff_in_seconds, validate_email_address
from mail.mail.doctype.spam_check_log.spam_check_log import create_spam_check_log
from mail.utils import (
	enqueue_job,
	parse_iso_datetime,
	get_in_reply_to_mail,
)
from mail.utils.user import (
	is_postmaster,
	is_mailbox_owner,
	is_system_manager,
	get_user_mailboxes,
)


if TYPE_CHECKING:
	from mail.mail.doctype.outgoing_mail.outgoing_mail import OutgoingMail


class IncomingMail(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		if self.get("_action") == "submit":
			self.spam_check()
			self.process()

	def on_submit(self) -> None:
		self.create_mail_contact()
		self.sync_with_frontend()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Incoming Mail."))

	def spam_check(self) -> None:
		"""Checks if the mail is spam."""

		mail_settings = frappe.get_cached_doc("Mail Settings")
		if mail_settings.enable_spam_detection and mail_settings.scan_incoming_mail:
			spam_log = create_spam_check_log(self.message)
			self.spam_score = spam_log.spam_score
			self.spam_check_response = spam_log.spamd_response
			self.is_spam = cint(self.spam_score > mail_settings.max_spam_score_for_inbound)

	def process(self) -> None:
		"""Processes the Incoming Mail."""

		parser = EmailParser(self.message)
		self.display_name, self.sender = parser.get_sender()

		self.domain_name = None
		if self.receiver and len(self.receiver.split("@")) > 1:
			self.domain_name = self.receiver.split("@")[1]

		self.subject = parser.get_subject()
		self.reply_to = parser.get_reply_to()
		self.message_id = parser.get_message_id()
		self.created_at = parser.get_date()
		self.message_size = parser.get_size()
		self.from_ip, self.from_host = extract_ip_and_host(parser.get_header("Received"))
		self.received_at = parse_iso_datetime(parser.get_header("Received-At"))
		self.in_reply_to = parser.get_in_reply_to()
		self.in_reply_to_mail_type, self.in_reply_to_mail_name = get_in_reply_to_mail(
			self.in_reply_to
		)

		parser.save_attachments(self.doctype, self.name, is_private=True)
		self.body_html, self.body_plain = parser.get_body()

		for recipient in parser.get_recipients():
			self.append("recipients", recipient)

		for key, value in parser.get_authentication_results().items():
			setattr(self, key, value)

		self.folder = "Spam" if self.is_spam else "Inbox"
		self.status = "Rejected" if self.is_rejected else "Accepted"

		if self.created_at:
			self.received_after = time_diff_in_seconds(self.received_at, self.created_at)

		self.processed_at = now()
		self.processed_after = time_diff_in_seconds(self.processed_at, self.received_at)

	def create_mail_contact(self) -> None:
		"""Creates the mail contact."""

		if ("dmarc@" not in self.receiver) and frappe.get_cached_value(
			"Mailbox", self.receiver, "create_mail_contact"
		):
			user = frappe.get_cached_value("Mailbox", self.receiver, "user")
			create_mail_contact(user, self.sender, self.display_name)

	def sync_with_frontend(self) -> None:
		"""Syncs the Incoming Mail with the frontend."""

		frappe.publish_realtime(
			"incoming_mail_received", self.as_dict(), user=self.receiver, after_commit=True
		)


@frappe.whitelist()
def reply_to_mail(source_name, target_doc=None) -> "OutgoingMail":
	"""Creates an Outgoing Mail as a reply to the Incoming Mail."""

	in_reply_to_mail_type = "Incoming Mail"
	source_doc = frappe.get_doc(in_reply_to_mail_type, source_name)
	target_doc = target_doc or frappe.new_doc("Outgoing Mail")

	target_doc.in_reply_to_mail_type = source_doc.doctype
	target_doc.in_reply_to_mail_name = source_name
	target_doc.subject = f"Re: {source_doc.subject}"

	email = source_doc.sender
	display_name = source_doc.display_name

	if source_doc.reply_to:
		display_name, email = parseaddr(source_doc.reply_to)

	target_doc.append(
		"recipients",
		{"type": "To", "email": email, "display_name": display_name},
	)

	if frappe.flags.args.all:
		recipients = [email, source_doc.receiver]
		for recipient in source_doc.recipients:
			if (recipient.type in ["To", "Cc"]) and (recipient.email not in recipients):
				recipients.append(recipient.email)
				target_doc.append(
					"recipients",
					{
						"type": "Cc",
						"email": recipient.email,
						"display_name": recipient.display_name,
					},
				)

	return target_doc


@frappe.whitelist()
def delete_incoming_mails(mailbox: str) -> None:
	"""Deletes the incoming mails for the given mailbox."""

	if not is_system_manager(frappe.session.user):
		frappe.throw(_("Only System Manager can delete Incoming Mails."))

	if mailbox:
		frappe.db.delete("Incoming Mail", {"receiver": mailbox})


def delete_rejected_mails() -> None:
	"""Called by the scheduler to delete the rejected mails based on the retention."""

	from frappe.query_builder import Interval
	from frappe.query_builder.functions import Now

	retention_days = frappe.db.get_single_value(
		"Mail Settings", "rejected_mail_retention", cache=True
	)
	IM = frappe.qb.DocType("Incoming Mail")
	(
		frappe.qb.from_(IM)
		.where(
			(IM.docstatus != 0)
			& (IM.is_rejected == 1)
			& (IM.processed_at < (Now() - Interval(days=retention_days)))
		)
		.delete()
	).run()


def has_permission(doc: "Document", ptype: str, user: str) -> bool:
	if doc.doctype != "Incoming Mail":
		return False

	user_is_mailbox_user = is_mailbox_owner(doc.receiver, user)
	user_is_system_manager = is_postmaster(user) or is_system_manager(user)

	if ptype in ["create", "submit"]:
		return user_is_system_manager
	elif ptype in ["write", "cancel"]:
		return user_is_system_manager or user_is_mailbox_user
	else:
		return user_is_system_manager or (user_is_mailbox_user and doc.docstatus == 1)


def get_permission_query_condition(user: str | None = None) -> str:
	if not user:
		user = frappe.session.user

	if is_system_manager(user):
		return ""

	if mailboxes := ", ".join(repr(m) for m in get_user_mailboxes(user)):
		return f"(`tabIncoming Mail`.`receiver` IN ({mailboxes})) AND (`tabIncoming Mail`.`docstatus` = 1)"
	else:
		return "1=0"


def is_active_domain(domain_name: str) -> bool:
	"""Returns True if the domain is active, otherwise False."""

	return bool(
		frappe.db.exists("Mail Domain", {"domain_name": domain_name, "enabled": 1})
	)


def is_mail_alias(alias: str) -> bool:
	"""Returns True if the mail alias exists, otherwise False."""

	return bool(frappe.db.exists("Mail Alias", alias))


def is_active_mail_alias(alias: str) -> bool:
	"""Returns True if the mail alias is active, otherwise False."""

	return bool(frappe.db.exists("Mail Alias", {"alias": alias, "enabled": 1}))


def is_active_mailbox(mailbox: str) -> bool:
	"""Returns True if the mailbox is active, otherwise False."""

	return bool(frappe.db.exists("Mailbox", {"email": mailbox, "enabled": 1}))


def get_rejected_template(incoming_mail) -> str:
	"""Returns the rejected HTML template."""

	# TODO: Create a better HTML template
	body_html = f"""
	<!DOCTYPE html>
	<html lang="en">
	<head>
		<meta charset="UTF-8">
		<meta name="viewport" content="width=device-width, initial-scale=1.0">
		<title>Document</title>
	</head>
	<body>
		<div>
			<h2>Your message to {incoming_mail.receiver} couldn't be delivered.</h2>
			<hr/>
			<h3>{incoming_mail.rejection_message}</h3>
			<hr/>
			<div>
				<p>Original Message Headers</p>
				<br/><br/>
				<code>{incoming_mail.message}</code>
			</div>
		</div>
	</body>
	</html>
	"""

	return body_html


def create_incoming_mail(
	agent: str,
	receiver: str,
	message: str,
	is_rejected: int = 0,
	rejection_message: str | None = None,
	do_not_save: bool = False,
	do_not_submit: bool = False,
) -> "IncomingMail":
	"""Creates an Incoming Mail."""

	doc = frappe.new_doc("Incoming Mail")
	doc.agent = agent
	doc.receiver = receiver
	doc.message = message
	doc.is_rejected = is_rejected
	doc.rejection_message = rejection_message

	if not do_not_save:
		doc.flags.ignore_links = True
		doc.save()
		if not do_not_submit:
			try:
				doc.submit()
			except Exception:
				frappe.log_error(
					title="Submit Incoming Mail",
					message=frappe.get_traceback(with_context=False),
				)

	return doc


def get_incoming_mails() -> None:
	"""Gets incoming mails from the RabbitMQ."""

	def process_incoming_mail(agent: str, message: str) -> None:
		"""Processes the incoming mail message."""

		parsed_message = EmailParser.get_parsed_message(message)
		receiver = parsed_message.get("Delivered-To")
		display_name, sender = parseaddr(parsed_message.get("From"))

		if not (validate_email_address(sender) == sender) or not (
			validate_email_address(receiver) == receiver
		):
			frappe.log_error(title="Invalid Email Address", message=message)
			return

		domain_name = receiver.split("@")[1]

		if not is_active_domain(domain_name):
			log_rejected_mail(agent, receiver, message)
			return

		if is_mail_alias(receiver):
			mail_alias = frappe.get_cached_doc("Mail Alias", receiver)
			if mail_alias.enabled:
				for mailbox in mail_alias.mailboxes:
					if is_active_mailbox(mailbox.mailbox):
						create_incoming_mail(agent, mailbox.mailbox, message)
		elif is_active_mailbox(receiver):
			create_incoming_mail(agent, receiver, message)
			return

		# If not accepted by alias or mailbox, reject the email
		log_rejected_mail(agent, receiver, message)

	def log_rejected_mail(agent: str, receiver: str, message: str) -> None:
		"""Logs the rejected mail."""

		incoming_mail = create_incoming_mail(
			agent,
			receiver,
			message,
			is_rejected=1,
			rejection_message="550 5.4.1 Recipient address rejected: Access denied.",
		)

		if incoming_mail.docstatus == 1 and frappe.db.get_single_value(
			"Mail Settings", "send_notification_on_reject", cache=True
		):
			try:
				create_outgoing_mail(
					sender=get_postmaster(),
					to=incoming_mail.reply_to or incoming_mail.sender,
					display_name="Mail Delivery System",
					subject=f"Undeliverable: {incoming_mail.subject}",
					body_html=get_rejected_template(incoming_mail),
				)
			except Exception:
				frappe.log_error(
					title="Send Rejection Notification",
					message=frappe.get_traceback(with_context=False),
				)

	from mail.config.constants import INCOMING_MAIL_QUEUE

	frappe.session.user = get_postmaster()

	try:
		with rabbitmq_context() as rmq:
			rmq.declare_queue(INCOMING_MAIL_QUEUE)

			while True:
				result = rmq.basic_get(INCOMING_MAIL_QUEUE)

				if result:
					method, properties, body = result
					if body:
						message = body.decode("utf-8")
						process_incoming_mail(properties.app_id, message)

					rmq.channel.basic_ack(delivery_tag=method.delivery_tag)
				else:
					break
	except Exception:
		frappe.log_error(
			title="Get Incoming Mails",
			message=frappe.get_traceback(with_context=False),
		)


@frappe.whitelist()
def enqueue_get_incoming_mails() -> None:
	"Called by the scheduler to enqueue the `get_incoming_mails` job."

	frappe.session.user = get_postmaster()
	enqueue_job(get_incoming_mails, queue="long")
