# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import dkim
import frappe
import string
import secrets
import smtplib
import email.utils
from datetime import datetime
from email.mime.text import MIMEText
from frappe.model.document import Document
from email.mime.multipart import MIMEMultipart


class FMQueue(Document):
	def autoname(self) -> None:
		self.name = "{0}.{1}".format(
			datetime.now().strftime("%Y%m%d%H%M%S"),
			"".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(11)),
		)

	def after_insert(self) -> None:
		self.sendmail()

	def add_recipients(self, recipients: list) -> None:
		for recipient in recipients:
			self.append("recipients", {"recipient": recipient})

	def get_recipients(self) -> None:
		return [d.recipient for d in self.recipients]

	def sendmail(self, ignore_status: bool = False) -> None:
		if self.status != "Draft" and not ignore_status:
			return

		fm_settings = frappe.get_cached_doc("FM Settings")
		fm_domain = frappe.get_cached_doc("FM Domain", self.domain_name)
		display_name = frappe.get_cached_value("FM Mailbox", self.sender, "display_name")

		message = MIMEMultipart("alternative")
		message["From"] = "{0} <{1}>".format(display_name, self.sender) if display_name else self.sender
		message["To"] = ", ".join(self.get_recipients())
		message["Subject"] = self.subject
		message["Date"] = email.utils.formatdate()
		message["Message-ID"] = "<{0}@{1}>".format(self.name, fm_settings.smtp_server)

		if self.body:
			if isinstance(self.body, bytes):
				self.body = self.body.decode()

			message.attach(MIMEText(self.body, "html"))

		msg_data = message.as_bytes()
		headers = [b"To", b"From", b"Subject"]
		signature = dkim.sign(
			message=msg_data,
			selector=str(fm_domain.dkim_selector).encode(),
			domain=fm_domain.domain_name.encode(),
			privkey=fm_domain.get_password("dkim_private_key").encode(),
			include_headers=headers,
		)
		message["DKIM-Signature"] = signature[len("DKIM-Signature: ") :].decode()

		with smtplib.SMTP(fm_settings.smtp_server, fm_settings.smtp_port) as server:
			if fm_settings.use_tls:
				server.starttls()

			server.ehlo(self.domain_name)
			server.send_message(message)
			self.db_set("status", "Queued")
