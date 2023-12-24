# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FMSettings(Document):
	def validate(self):
		self.validate_default_dkim_bits()

	def validate_default_dkim_bits(self):
		if self.default_dkim_bits < 1024:
			frappe.throw(_("DKIM Bits must be greater than 1024."))
