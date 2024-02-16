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
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job

if TYPE_CHECKING:
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class OutgoingMail(Document):
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
		display_name = frappe.get_cached_value("Mailbox", self.sender, "display_name")
		dkim_selector = frappe.get_cached_value(
			"Mail Domain", self.domain_name, "dkim_selector"
		)
		dkim_private_key = get_decrypted_password(
			"Mail Domain", self.domain_name, "dkim_private_key"
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

	def get_recipients(self) -> None:
		return [d.recipient for d in self.recipients]

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify_update: bool = False,
		**kwargs
	) -> None:
		self.db_set(kwargs, update_modified=update_modified, commit=commit)

		if notify_update:
			self.notify_update()


def update_delivery_status(agent_job: "MailAgentJob") -> None:
	if agent_job.job_type != "Send Mail":
		return

	status = "Sent" if agent_job.status == "Completed" else "Failed"
	original_message = json.loads(agent_job.request_data).get("data")
	parsed_message = Parser(policy=policy.default).parsestr(original_message)
	message_id = parsed_message["Message-ID"].split("@")[0].replace("<", "")

	if status == "Sent":
		RECIPIENT = frappe.qb.DocType("Mail Recipient")
		(
			frappe.qb.update(RECIPIENT)
			.set("sent", 1)
			.where(
				(RECIPIENT.sent == 0)
				& (RECIPIENT.parent == message_id)
				& (RECIPIENT.parenttype == "Outgoing Mail")
			)
		).run()

	outgoing_mail = frappe.get_doc("Outgoing Mail", message_id)
	outgoing_mail._db_set(status=status, error_log=agent_job.error_log, notify_update=True)
