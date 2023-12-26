# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FMMailbox(Document):
	def validate(self):
		self.validate_display_name()

	def validate_display_name(self):
		if self.is_new() and not self.display_name:
			self.display_name = frappe.get_cached_value("User", self.user, "full_name")
