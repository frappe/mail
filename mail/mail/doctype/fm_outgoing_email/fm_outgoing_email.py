# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from mail.send import sendmail
from mail.utils import get_outgoing_server
from frappe.model.document import Document


class FMOutgoingEmail(Document):
	def autoname(self) -> None:
		import string
		import secrets
		from datetime import datetime

		self.name = "{0}.{1}".format(
			datetime.now().strftime("%Y%m%d%H%M%S"),
			"".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(11)),
		)

	def validate(self) -> None:
		self.validate_server()

	def after_insert(self) -> None:
		self.enqueue_sendmail()

	def validate_server(self) -> None:
		if not self.server:
			self.server = get_outgoing_server()

	def add_recipients(self, recipients: list) -> None:
		for recipient in recipients:
			self.append("recipients", {"recipient": recipient})

	def get_recipients(self) -> None:
		return [d.recipient for d in self.recipients]

	def update_status(self, status: str, error_log: str = None) -> None:
		if status == "Sent":
			for recipient in self.recipients:
				recipient.db_set("sent", 1)

		if status == "Failed":
			self.error_log = error_log

		self.status = status
		self.db_update()

	def enqueue_sendmail(self) -> None:
		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"sendmail",
			timeout=600,
			enqueue_after_commit=True,
		)

	def sendmail(self) -> None:
		try:
			sendmail(self)
			self.update_status("Sent")
		except Exception:
			error_log = frappe.log_error(title="FM Outgoing Email")
			self.update_status(status="Failed", error_log=error_log.name)
