# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import dkim
import frappe
import smtplib
from mail.utils import Utils
from email.utils import formatdate
from email.mime.text import MIMEText
from frappe.model.document import Document
from email.mime.multipart import MIMEMultipart


class FMQueue(Document):
	def autoname(self) -> None:
		import string
		import secrets
		from datetime import datetime

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

		smtp_server = Utils.get_smtp_server()
		fm_domain = frappe.get_cached_doc("FM Domain", self.domain_name)
		display_name = frappe.get_cached_value("FM Mailbox", self.sender, "display_name")

		message = MIMEMultipart("alternative")
		message["From"] = (
			"{0} <{1}>".format(display_name, self.sender) if display_name else self.sender
		)
		message["To"] = ", ".join(self.get_recipients())
		message["Subject"] = self.subject
		message["Date"] = formatdate()
		message["Message-ID"] = "<{0}@{1}>".format(self.name, smtp_server.server)

		if self.body:
			message.attach(MIMEText(self.body, "html"))

		headers = [b"To", b"From", b"Subject"]
		signature = dkim.sign(
			message=message.as_bytes(),
			domain=fm_domain.domain_name.encode(),
			selector=fm_domain.dkim_selector.encode(),
			privkey=fm_domain.get_password("dkim_private_key").encode(),
			include_headers=headers,
		)
		message["DKIM-Signature"] = signature[len("DKIM-Signature: ") :].decode()

		with smtplib.SMTP(smtp_server.host or smtp_server.server, smtp_server.port) as server:
			if smtp_server.use_tls:
				server.starttls()

			if smtp_server.username and smtp_server.password:
				server.login(smtp_server.username, smtp_server.get_password("password"))

			server.ehlo(self.domain_name)
			server.send_message(message)
			self.db_set("status", "Queued")
