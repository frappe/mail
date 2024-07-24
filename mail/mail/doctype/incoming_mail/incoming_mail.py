# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from uuid_utils import uuid7
from typing import TYPE_CHECKING
from email.utils import parseaddr
from mail.utils import parse_iso_datetime
from frappe.model.document import Document
from mail.utils.email_parser import EmailParser
from frappe.utils import now, time_diff_in_seconds
from mail.utils.agent import get_agent_rabbitmq_connection
from mail.mail.doctype.mail_contact.mail_contact import create_mail_contact
from mail.mail.doctype.outgoing_mail.outgoing_mail import create_outgoing_mail
from mail.utils.user import (
	is_postmaster,
	get_postmaster,
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
			self.process()

	def on_submit(self) -> None:
		self.create_mail_contact()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Incoming Mail."))

	def process(self) -> None:
		"""Processes the Incoming Mail."""

		parser = EmailParser(self.message)

		self.display_name, self.sender = parser.get_sender()
		self.subject = parser.get_subject()
		self.reply_to = parser.get_header("Reply-To")
		self.message_id = parser.get_header("Message-ID")
		self.created_at = parser.get_date()
		self.message_size = parser.get_size()
		self.received_at = parse_iso_datetime(parser.get_header("Received-At"))

		parser.save_attachments(self.doctype, self.name, is_private=True)
		self.body_html, self.body_plain = parser.get_body()

		for recipient in parser.get_recipients():
			self.append("recipients", recipient)

		for key, value in parser.get_authentication_results().items():
			setattr(self, key, value)

		if in_reply_to := parser.get_header("In-Reply-To"):
			for reply_to_mail_type in ["Outgoing Mail", "Incoming Mail"]:
				if reply_to_mail_name := frappe.get_cached_value(
					reply_to_mail_type, in_reply_to, "name"
				):
					self.reply_to_mail_type = reply_to_mail_type
					self.reply_to_mail_name = reply_to_mail_name
					break

		self.status = "Rejected" if self.is_rejected else "Delivered"
		self.processed_at = now()
		self.received_after = time_diff_in_seconds(self.received_at, self.created_at)
		self.processed_after = time_diff_in_seconds(self.processed_at, self.received_at)

	def create_mail_contact(self) -> None:
		"""Creates the mail contact."""

		if ("dmarc@" not in self.receiver) and frappe.get_cached_value(
			"Mailbox", self.receiver, "create_mail_contact"
		):
			user = frappe.get_cached_value("Mailbox", self.receiver, "user")
			create_mail_contact(user, self.sender, self.display_name)


@frappe.whitelist()
def reply_to_mail(source_name, target_doc=None) -> "OutgoingMail":
	"""Creates an Outgoing Mail as a reply to the Incoming Mail."""

	reply_to_mail_type = "Incoming Mail"
	source_doc = frappe.get_doc(reply_to_mail_type, source_name)
	target_doc = target_doc or frappe.new_doc("Outgoing Mail")

	target_doc.reply_to_mail_type = source_doc.doctype
	target_doc.reply_to_mail_name = source_name
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


@frappe.whitelist()
def get_incoming_mails() -> None:
	"""Called by the scheduler to get incoming mails from the mail agents."""

	frappe.session.user = get_postmaster()
	agents = frappe.db.get_all(
		"Mail Agent", filters={"enabled": 1, "incoming": 1}, pluck="name"
	)

	for agent in agents:
		frappe.enqueue(
			get_incoming_mails_from_agent,
			queue="long",
			is_async=True,
			now=False,
			job_name=f"Get Incoming Mails - {agent}",
			enqueue_after_commit=False,
			at_front=False,
			agent=agent,
		)


def get_incoming_mails_from_agent(agent: str) -> None:
	"""Gets incoming mails from the mail agent."""

	def callback(channel, method, properties, body) -> bool:
		"""Callback function for the RabbitMQ consumer."""

		is_accepted = False
		message = body.decode("utf-8")
		parsed_message = EmailParser.get_parsed_message(message)
		receiver = parsed_message.get("Delivered-To")

		if receiver and "@" in receiver:
			domain_name = receiver.split("@")[1]

			if is_active_domain(domain_name):
				if is_mail_alias(receiver):
					mail_alias = frappe.get_cached_doc("Mail Alias", receiver)
					if mail_alias.enabled:
						is_accepted = True
						for mailbox in mail_alias.mailboxes:
							if is_active_mailbox(mailbox.mailbox):
								create_incoming_mail(agent, mailbox.mailbox, message)
				elif is_active_mailbox(receiver):
					is_accepted = True
					create_incoming_mail(agent, receiver, message)

		if not is_accepted:
			incoming_mail = create_incoming_mail(
				agent,
				receiver,
				message,
				is_rejected=True,
				rejection_message="550 5.4.1 Recipient address rejected: Access denied.",
			)

			# TODO: Create a better HTML template
			raw_html = f"""
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

			create_outgoing_mail(
				sender=get_postmaster(),
				to=incoming_mail.reply_to or incoming_mail.sender,
				display_name="Mail Delivery System",
				subject=f"Undeliverable: {incoming_mail.subject}",
				raw_html=raw_html,
			)

		channel.basic_ack(delivery_tag=method.delivery_tag)
		return True

	from mail.config.constants import INCOMING_MAIL_QUEUE

	try:
		rmq = get_agent_rabbitmq_connection(agent)
		rmq.declare_queue(INCOMING_MAIL_QUEUE)

		while True:
			if not rmq.basic_get(INCOMING_MAIL_QUEUE, callback=callback):
				break
	except Exception:
		frappe.log_error(
			title=f"Get Incoming Mails - {agent}",
			message=frappe.get_traceback(with_context=False),
		)


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


def create_incoming_mail(
	agent: str,
	receiver: str,
	message: str,
	is_rejected: bool = False,
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
			doc.submit()

	return doc
