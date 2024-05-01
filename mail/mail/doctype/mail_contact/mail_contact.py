# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MailContact(Document):
	def before_validate(self) -> None:
		self.set_user()

	def set_user(self) -> None:
		"""Set user as current user if not set."""

		self.user = self.user or frappe.session.user
