# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import email
import frappe
from frappe import _
from typing import Optional
from frappe.utils import cint
from typing import TYPE_CHECKING
from frappe.model.document import Document
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from frappe.core.doctype.submission_queue.submission_queue import queue_submission

if TYPE_CHECKING:
	from email.message import Message
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class IncomingMail(Document):
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
		def __get_body(parsed_message: "Message") -> tuple[str, str]:
			body_html, body_plain = "", ""

			for part in parsed_message.walk():
				content_type = part.get_content_type()

				if content_type == "text/html":
					if payload := part.get_payload(decode=True):
						body_html += payload.decode(part.get_content_charset(), "ignore")

				elif content_type == "text/plain":
					if payload := part.get_payload(decode=True):
						body_plain += payload.decode(part.get_content_charset(), "ignore")

			return body_html, body_plain

		parsed_message = email.message_from_string(self.original_message)
		sender = email.utils.parseaddr(parsed_message["From"])

		self.sender = sender[1]
		self.display_name = sender[0]
		self.recipient = parsed_message["To"]
		self.subject = parsed_message["Subject"]
		self.message_id = parsed_message["Message-ID"]
		self.body_html, self.body_plain = __get_body(parsed_message)

		self.spf_description = parsed_message.get("Received-SPF") or parsed_message.get(
			"X-Comment"
		)
		if self.spf_description:
			spf_description_lower = self.spf_description.lower()
			self.spf = cint(
				"pass" in spf_description_lower
				or "SPF check N/A for local connections".lower() in spf_description_lower
			)

		if headers := parsed_message.get_all("Authentication-Results"):
			for header in headers:
				header_lower = header.lower()

				if "dkim=" in header_lower:
					if "pass" in header_lower:
						self.dkim = 1
					self.dkim_description = header

				elif "dmarc=" in header_lower:
					if "pass" in header_lower:
						self.dmarc = 1
					self.dmarc_description = header


def insert_incoming_mails(agent_job: "MailAgentJob") -> None:
	if agent_job and agent_job.job_type == "Receive Mails":
		if agent_job.status == "Completed":
			if mails := json.loads(agent_job.response_data)["message"]:
				for mail in mails:
					doc = frappe.new_doc("Incoming Mail")
					doc.server = agent_job.server
					doc.eml_filename = mail["eml_filename"]
					doc.original_message = mail["original_message"]
					doc.save()
					queue_submission(doc, "submit", alert=False)


@frappe.whitelist()
def sync_incoming_mails(servers: Optional[str | list] = None) -> None:
	if not servers:
		servers = frappe.db.get_all(
			"Mail Server", {"enabled": 1, "incoming": 1}, pluck="name"
		)
	elif isinstance(servers, str):
		servers = [servers]

	for server in servers:
		create_agent_job(server, "Receive Mails")
