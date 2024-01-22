# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from mail.utils import Utils
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

	def validate_server(self) -> None:
		if not self.server:
			self.server = Utils.get_outgoing_server()

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
