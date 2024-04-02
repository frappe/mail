# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import re
import json
import email
import frappe
from frappe import _
from typing import Optional
from typing import TYPE_CHECKING
from frappe.model.document import Document
from mail.utils import parsedate_to_datetime
from frappe.utils.file_manager import save_file
from frappe.utils import (
	now,
	cint,
	format_duration,
	get_datetime_str,
	time_diff_in_seconds,
)
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from frappe.core.doctype.submission_queue.submission_queue import queue_submission

if TYPE_CHECKING:
	from email.message import Message
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class IncomingMail(Document):
	def onload(self):
		self.received_in = format_duration(self.received_after, hide_days=True)
		self.delivered_in = format_duration(self.delivered_after, hide_days=True)

	def validate(self) -> None:
		self.validate_mandatory_fields()
		if self.get("_action") == "submit":
			self.process()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Incoming Mail."))

	def validate_mandatory_fields(self) -> None:
		mandatory_fields = [
			"original_message",
			"eml_filename",
			"status",
		]

		for field in mandatory_fields:
			if not self.get(field):
				frappe.throw(f"{field} is mandatory")

	def process(self) -> None:
		def __add_attachment(
			filename: str, content: bytes, is_private: bool = 1, for_doc: bool = True
		) -> dict:
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

		def __get_body(parsed_message: "Message") -> tuple[str, str]:
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

								file = __add_attachment(filename, payload, is_private=0, for_doc=False)
								body_html = body_html.replace("cid:" + content_id, file["file_url"])

					elif disposition.startswith("attachment"):
						__add_attachment(filename, part.get_payload(decode=True))

				elif content_type == "text/html":
					body_html += part.get_payload(decode=True).decode(
						part.get_content_charset(), "ignore"
					)

				elif content_type == "text/plain":
					body_plain += part.get_payload(decode=True).decode(
						part.get_content_charset(), "ignore"
					)

			return body_html, body_plain

		parsed_message = email.message_from_string(self.original_message)
		sender = email.utils.parseaddr(parsed_message["From"])

		self.sender = sender[1]
		self.display_name = sender[0]
		self.receiver = parsed_message["Delivered-To"]
		self.recipients = parsed_message["To"]
		self.subject = parsed_message["Subject"]
		self.message_id = parsed_message["Message-ID"]
		self.body_html, self.body_plain = __get_body(parsed_message)
		self.created_at = get_datetime_str(parsedate_to_datetime(parsed_message["Date"]))

		self.spf_description = parsed_message.get("Received-SPF")
		if self.spf_description:
			self.spf = cint("pass" in self.spf_description.lower())
		else:
			self.spf = 1
			self.spf_description = "Internal Network"

		if headers := parsed_message.get_all("Authentication-Results"):
			for header in headers:
				header_lower = header.lower()

				if "dkim=" in header_lower:
					if "dkim=pass" in header_lower:
						self.dkim = 1
					self.dkim_description = header

				elif "dmarc=" in header_lower:
					if "dmarc=pass" in header_lower:
						self.dmarc = 1
					self.dmarc_description = header

		self.status = "Delivered"
		self.delivered_at = now()
		self.received_after = time_diff_in_seconds(self.received_at, self.created_at)
		self.delivered_after = time_diff_in_seconds(self.delivered_at, self.received_at)


@frappe.whitelist()
def get_incoming_mails(servers: Optional[str | list] = None) -> None:
	if not servers:
		servers = frappe.db.get_all(
			"Mail Server", {"enabled": 1, "incoming": 1}, pluck="name"
		)
	elif isinstance(servers, str):
		servers = [servers]

	for server in servers:
		create_agent_job(server, "Get Incoming Mails")


def insert_incoming_mails(agent_job: "MailAgentJob") -> None:
	if agent_job and agent_job.job_type == "Get Incoming Mails":
		if agent_job.status == "Completed":
			if mails := json.loads(agent_job.response_data)["message"]:
				for mail in mails:
					doc = frappe.new_doc("Incoming Mail")
					doc.server = agent_job.server
					doc.received_at = mail["received_at"]
					doc.eml_filename = mail["eml_filename"]
					doc.original_message = mail["original_message"]
					doc.save()
					queue_submission(doc, "submit", alert=False)
