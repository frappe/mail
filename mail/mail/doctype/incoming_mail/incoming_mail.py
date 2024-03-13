# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import re
import spf
import dkim
import json
import email
import frappe
from frappe import _
from typing import Optional
from typing import TYPE_CHECKING
from frappe.model.document import Document
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job

if TYPE_CHECKING:
	from email.message import Message
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class IncomingMail(Document):
	def validate(self) -> None:
		if self.get("_action") == "submit":
			self.process()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Incoming Mail."))

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

		def __spf_check(
			sender: str, received_header: str | list
		) -> tuple[bool, Optional[str]]:
			try:
				if not received_header:
					return False, "No Received headers found"

				if isinstance(received_header, list):
					received_header = received_header[0]

				ip, server = None, None

				if i_match := re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", received_header):
					if ip := i_match.group(0):
						ip = ip.replace("[", "").replace("]", "").strip()
				else:
					return False, "No IP address found"

				if s_match := re.search(r"(?<=from\s)[^\s()]+(?=\s)", received_header):
					server = s_match.group(0)
				else:
					return False, "No mail server found"

				result = spf.check2(i=ip, s=sender, h=server)

				return True if result and result[0] == "pass" else False, None

			except Exception as e:
				return False, str(e)

		def __dkim_check(original_message: str) -> tuple[bool, Optional[str]]:
			try:
				return (
					dkim.DKIM(
						original_message.encode("utf-8"), minkey=1024, timeout=5, tlsrpt=False
					).verify(),
					None,
				)
			except Exception as e:
				return False, str(e)

		parsed_message = email.message_from_string(self.original_message)
		sender = email.utils.parseaddr(parsed_message["From"])

		self.sender = sender[1]
		self.display_name = sender[0]
		self.recipient = parsed_message["To"]
		self.subject = parsed_message["Subject"]
		self.message_id = parsed_message["Message-ID"]
		self.body_html, self.body_plain = __get_body(parsed_message)
		self.spf, self.spf_error = __spf_check(
			self.sender, parsed_message.get_all("Received")
		)
		self.dkim, self.dkim_error = __dkim_check(self.original_message)


def insert_incoming_mails(agent_job: "MailAgentJob") -> None:
	if agent_job and agent_job.job_type == "Receive Mails":
		if agent_job.status == "Completed":
			if mails := json.loads(agent_job.response_data)["message"]:
				for mail in mails:
					doc = frappe.new_doc("Incoming Mail")
					doc.server = agent_job.server
					doc.original_message = mail["original_message"]
					doc.save()


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
