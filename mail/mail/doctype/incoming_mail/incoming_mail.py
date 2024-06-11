# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import re
import json
import frappe
from frappe import _
from uuid_utils import uuid7
from email.utils import parseaddr
from email.header import decode_header
from typing import Optional, TYPE_CHECKING
from frappe.model.document import Document
from frappe.utils.file_manager import save_file
from frappe.utils import (
	now,
	get_datetime_str,
	time_diff_in_seconds,
)
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from frappe.core.doctype.submission_queue.submission_queue import queue_submission
from mail.utils import (
	is_postmaster,
	is_mailbox_owner,
	is_system_manager,
	get_user_mailboxes,
	get_parsed_message,
	validate_mail_folder,
	parsedate_to_datetime,
)

if TYPE_CHECKING:
	from email.message import Message
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
		print(self.as_dict())
		print(self.doctype)
		for field in mandatory_fields:
			if not self.get(field):
				frappe.throw(_("{0} is mandatory").format(frappe.bold(field)))

	def validate_folder(self) -> None:
		"""Validates the folder"""

		if self.has_value_changed("folder"):
			validate_mail_folder(self.folder, validate_for="inbound")

	def process(self) -> None:
		"""Processes the Incoming Mail."""

		def _add_attachment(
			filename: str, content: bytes, is_private: bool = 1, for_doc: bool = True
		) -> dict:
			"""Add attachment to the Incoming Mail."""

			kwargs = {
				"fname": filename,
				"content": content,
				"is_private": is_private,
				"dt": None,
				"dn": None,
			}

			if for_doc:
				kwargs["dt"] = self.doctype
				kwargs["dn"] = self.name
				kwargs["df"] = "file"

			file = save_file(**kwargs)

			return {
				"name": file.name,
				"file_name": file.file_name,
				"file_url": file.file_url,
				"is_private": file.is_private,
			}

		def _get_body(parsed_message: "Message") -> tuple[str, str]:
			"""Returns the HTML and plain text body from the parsed message."""

			body_html, body_plain = "", ""

			for part in parsed_message.walk():
				filename = part.get_filename()
				content_type = part.get_content_type()
				disposition = part.get("Content-Disposition")

				if disposition and filename:
					disposition = disposition.lower()

					if disposition.startswith("inline"):
						if content_id := re.sub(r"[<>]", "", part.get("Content-ID", "")):
							if payload := part.get_payload(decode=True):
								if part.get_content_charset():
									payload = payload.decode(part.get_content_charset(), "ignore")

								file = _add_attachment(filename, payload, is_private=0, for_doc=False)
								body_html = body_html.replace("cid:" + content_id, file["file_url"])
								body_plain = body_plain.replace("cid:" + content_id, file["file_url"])

					elif disposition.startswith("attachment"):
						_add_attachment(filename, part.get_payload(decode=True))

				elif content_type == "text/html":
					body_html += part.get_payload(decode=True).decode(
						part.get_content_charset(), "ignore"
					)

				elif content_type == "text/plain":
					body_plain += part.get_payload(decode=True).decode(
						part.get_content_charset() or "utf-8", "ignore"
					)

			return body_html, body_plain

		parsed_message = get_parsed_message(self.message)
		sender = parseaddr(parsed_message["From"])

		self.sender = sender[1]
		self.display_name = sender[0]
		self.reply_to = parsed_message["Reply-To"]
		self.receiver = parsed_message["Delivered-To"]
		self._add_recipients(parsed_message)
		self.subject = decode_header(parsed_message["Subject"])[0][0]
		self.message_id = parsed_message["Message-ID"]
		self.body_html, self.body_plain = _get_body(parsed_message)
		self.created_at = get_datetime_str(parsedate_to_datetime(parsed_message["Date"]))

		if in_reply_to := parsed_message["In-Reply-To"]:
			if reply_to_mail := frappe.db.get_value("Outgoing Mail", in_reply_to, "name"):
				self.reply_to_mail_type = "Outgoing Mail"
				self.reply_to_mail = reply_to_mail
			elif reply_to_mail := frappe.db.get_value("Incoming Mail", in_reply_to, "name"):
				self.reply_to_mail_type = "Incoming Mail"
				self.reply_to_mail = reply_to_mail

		if headers := parsed_message.get_all("Authentication-Results"):
			if len(headers) == 1:
				headers = headers[0].split(";")

			for header in headers:
				header = header.replace("\n", "").replace("\t", "")
				header_lower = header.lower()

				if "spf=" in header_lower:
					self.spf_description = header
					if "spf=pass" in header_lower:
						self.spf = 1

				elif "dkim=" in header_lower:
					self.dkim_description = header
					if "dkim=pass" in header_lower:
						self.dkim = 1

				elif "dmarc=" in header_lower:
					self.dmarc_description = header
					if "dmarc=pass" in header_lower:
						self.dmarc = 1

		no_header = "Header not found."
		if not self.spf_description:
			self.spf = 0
			self.spf_description = no_header
		if not self.dkim_description:
			self.dkim = 0
			self.dkim_description = no_header
		if not self.dmarc_description:
			self.dmarc = 0
			self.dmarc_description = no_header

		self.status = "Delivered"
		self.delivered_at = now()
		self.message_size = len(parsed_message.as_bytes())
		self.received_after = time_diff_in_seconds(self.received_at, self.created_at)
		self.delivered_after = time_diff_in_seconds(self.delivered_at, self.received_at)

	def _add_recipients(
		self, parsed_message: "Message", types: Optional[str | list] = None
	) -> None:
		"""Adds recipients to the Incoming Mail."""

		if not types:
			types = ["To", "Cc", "Bcc"]
		elif isinstance(types, str):
			types = [types]

		for type in types:
			if recipients := parsed_message.get(type):
				for recipient in recipients.split(","):
					display_name, email = parseaddr(recipient)
					if email:
						self.append(
							"recipients", {"type": type, "email": email, "display_name": display_name}
						)


@frappe.whitelist()
def reply_to_mail(source_name, target_doc=None):
	reply_to_mail_type = "Incoming Mail"
	source_doc = frappe.get_doc(reply_to_mail_type, source_name)
	target_doc = target_doc or frappe.new_doc("Outgoing Mail")

	target_doc.reply_to_mail_type = source_doc.doctype
	target_doc.reply_to_mail = source_name
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
