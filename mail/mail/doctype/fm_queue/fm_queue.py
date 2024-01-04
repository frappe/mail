# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import string
import secrets
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from frappe.model.document import Document
from email.mime.multipart import MIMEMultipart


class FMQueue(Document):
	def autoname(self):
		self.name = f"{0}.{1}".format(
			datetime.now().strftime("%Y%m%d%H%M%S"),
			"".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(11)),
		)

	def add_recipients(self, recipients: list):
		for recipient in recipients:
			self.append("recipients", {"recipient": recipient})

	def get_recipients(self):
		return [d.recipient for d in self.recipients]

	def get_smtp_details(self):
		return frappe._dict(
			{
				"server": frappe.db.get_single_value("FM Settings", "smtp_server", cache=True),
				"use_tls": frappe.db.get_single_value("FM Settings", "use_tls", cache=True),
				"port": frappe.db.get_single_value("FM Settings", "smtp_port", cache=True),
			}
		)

	def sendmail(self):
		msg = MIMEMultipart("alternative")
		msg["From"] = self.sender
		msg["To"] = ", ".join(self.get_recipients())
		msg["Subject"] = self.subject
		msg["Message-ID"] = f"<{self.name}@mail.bunniesbakery.in>"

		if self.body:
			if isinstance(self.body, bytes):
				self.body = self.body.decode()

			msg.attach(MIMEText(self.body, "html"))

		smtp_details = self.get_smtp_details()
		with smtplib.SMTP(smtp_details.server, smtp_details.port) as server:
			if smtp_details.use_tls:
				server.starttls()

			server.send_message(msg)
