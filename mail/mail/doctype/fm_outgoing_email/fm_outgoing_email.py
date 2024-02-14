# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import dkim
import json
import frappe
import string
import secrets
from email import policy
from datetime import datetime
from email.parser import Parser
from typing import TYPE_CHECKING
from email.utils import formatdate
from email.mime.text import MIMEText
from frappe.core.utils import html2text
from mail.utils import get_outgoing_server
from frappe.model.document import Document
from email.mime.multipart import MIMEMultipart
from frappe.utils.password import get_decrypted_password
from mail.mail.doctype.fm_agent_job.fm_agent_job import create_agent_job

if TYPE_CHECKING:
	from mail.mail.doctype.fm_agent_job.fm_agent_job import FMAgentJob


class FMOutgoingEmail(Document):
	def autoname(self) -> None:
		self.name = "{0}.{1}".format(
			datetime.now().strftime("%Y%m%d%H%M%S"),
			"".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(11)),
		)

	def validate(self) -> None:
		self.validate_server()
		self.validate_recipients()
		self.validate_body_html()
		self.validate_body_plain()
		self.set_original_message()

	def after_insert(self) -> None:
		self.sendmail()

	def validate_server(self) -> None:
		if not self.server:
			self.server = get_outgoing_server()

	def validate_recipients(self) -> None:
		recipients = []
		for recipient in self.recipients:
			if recipient.recipient not in recipients:
				recipients.append(recipient.recipient)
			else:
				frappe.throw(
					"Row #{0}: Duplicate recipient {1}.".format(
						recipient.idx, frappe.bold(recipient.recipient)
					)
				)

	def validate_body_html(self) -> None:
		if not self.body_html:
			self.body_html = ""

	def validate_body_plain(self) -> None:
		self.body_plain = html2text(self.body_html)

	def set_original_message(self) -> None:
		self.original_message = self.get_signed_message()

	def get_signed_message(self) -> str:
		display_name = frappe.get_cached_value("FM Mailbox", self.sender, "display_name")
		dkim_selector = frappe.get_cached_value(
			"FM Domain", self.domain_name, "dkim_selector"
		)
		dkim_private_key = get_decrypted_password(
			"FM Domain", self.domain_name, "dkim_private_key"
		)

		message = MIMEMultipart("alternative")
		message["From"] = (
			"{0} <{1}>".format(display_name, self.sender) if display_name else self.sender
		)
		message["To"] = ", ".join(self.get_recipients())
		message["Subject"] = self.subject
		message["Date"] = formatdate()
		message["Message-ID"] = "<{0}@{1}>".format(self.name, self.server)

		if self.custom_headers:
			for header in self.custom_headers:
				message.add_header(header.key, header.value)

		if self.body_html:
			message.attach(MIMEText(self.body_html, "html"))

		if self.body_plain:
			message.attach(MIMEText(self.body_plain, "plain"))

		headers = [b"To", b"From", b"Subject"]
		signature = dkim.sign(
			message=message.as_bytes(),
			domain=self.domain_name.encode(),
			selector=dkim_selector.encode(),
			privkey=dkim_private_key.encode(),
			include_headers=headers,
		)
		message["DKIM-Signature"] = signature[len("DKIM-Signature: ") :].decode()

		return message.as_string()

	def sendmail(self) -> None:
		create_agent_job(self.server, "Send Mail", self.original_message)

	def update_status(self, status: str, error_log: str = None) -> None:
		if status == "Sent":
			for recipient in self.recipients:
				recipient.db_set("sent", 1)

		if status == "Failed":
			self.error_log = error_log

		self.status = status
		self.db_update()

	def get_recipients(self) -> None:
		return [d.recipient for d in self.recipients]


def update_delivery_status(agent_job: "FMAgentJob") -> None:
	if agent_job.job_type != "Send Mail":
		return

	original_message = json.loads(agent_job.request_data).get("data")
	parsed_message = Parser(policy=policy.default).parsestr(original_message)
	outgoing_mail = parsed_message["Message-ID"].split("@")[0].replace("<", "")
	status = "Sent" if agent_job.status == "Completed" else "Failed"

	frappe.db.set_value(
		"FM Outgoing Email",
		outgoing_mail,
		{"status": status, "error_log": agent_job.error_log},
	)

	if status == "Sent":
		RECIPIENT = frappe.qb.DocType("FM Recipient")
		(
			frappe.qb.update(RECIPIENT)
			.set("sent", 1)
			.where((RECIPIENT.parent == outgoing_mail) & (RECIPIENT.sent == 0))
		).run()
