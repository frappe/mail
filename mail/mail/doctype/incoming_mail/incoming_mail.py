# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from uuid_utils import uuid7
from email.utils import parseaddr
from typing import Optional, TYPE_CHECKING
from frappe.model.document import Document
from mail.utils.email_parser import EmailParser
from frappe.utils import now, time_diff_in_seconds
from mail.utils.validation import validate_mail_folder
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from frappe.core.doctype.submission_queue.submission_queue import queue_submission
from mail.utils.user import (
	is_postmaster,
	is_system_manager,
	is_mailbox_owner,
	get_user_mailboxes,
)


if TYPE_CHECKING:
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class IncomingMail(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_mandatory_fields()
		self.validate_folder()

		if self.get("_action") == "submit":
			self.process()

	def on_update_after_submit(self) -> None:
		self.validate_folder()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Incoming Mail."))

	def validate_mandatory_fields(self) -> None:
		"""Validates mandatory fields."""

		mandatory_fields = [
			"status",
			"message",
		]

		for field in mandatory_fields:
			if not self.get(field):
				frappe.throw(_("{0} is mandatory").format(frappe.bold(field)))

	def validate_folder(self) -> None:
		"""Validates the folder"""

		if self.has_value_changed("folder"):
			validate_mail_folder(self.folder, validate_for="inbound")

	def process(self) -> None:
		"""Processes the Incoming Mail."""

		parser = EmailParser(self.message)

		self.display_name, self.sender = parser.get_sender()
		self.subject = parser.get_subject()
		self.reply_to = parser.get_header("Reply-To")
		self.receiver = parser.get_header("Delivered-To")
		self.message_id = parser.get_header("Message-ID")
		self.created_at = parser.get_date()
		self.message_size = parser.get_size()

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

		self.status = "Delivered"
		self.processed_at = now()
		self.received_after = time_diff_in_seconds(self.received_at, self.created_at)
		self.processed_after = time_diff_in_seconds(self.processed_at, self.received_at)


@frappe.whitelist()
def reply_to_mail(source_name, target_doc=None):
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


def get_permission_query_condition(user: Optional[str]) -> str:
	if not user:
		user = frappe.session.user

	if is_system_manager(user):
		return ""

	if mailboxes := ", ".join(repr(m) for m in get_user_mailboxes(user)):
		return f"(`tabIncoming Mail`.`receiver` IN ({mailboxes})) AND (`tabIncoming Mail`.`docstatus` = 1)"
	else:
		return "1=0"


@frappe.whitelist()
def sync_incoming_mails(agents: Optional[str | list] = None) -> None:
	"""Syncs incoming mails from the given agents."""

	if not agents:
		agents = frappe.db.get_all(
			"Mail Agent", filters={"enabled": 1, "incoming": 1}, pluck="name"
		)
	elif isinstance(agents, str):
		agents = [agents]

	for agent in agents:
		create_agent_job(agent, "Sync Incoming Mails")


def sync_incoming_mails_on_end(agent_job: "MailAgentJob") -> None:
	"""Called on the end of the `Sync Incoming Mails` job."""

	if agent_job and agent_job.job_type == "Sync Incoming Mails":
		if agent_job.status == "Completed":
			if mails := json.loads(agent_job.response_data)["message"]:
				for mail in mails:
					doc = frappe.new_doc("Incoming Mail")
					doc.agent = agent_job.agent
					doc.received_at = mail["received_at"]
					doc.eml_filename = mail["eml_filename"]
					doc.message = mail["message"]
					doc.insert()
					queue_submission(doc, "submit", alert=False)
