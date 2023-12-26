# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FMMailbox(Document):
	def validate(self):
		self.validate_domain()
		self.validate_email()
		self.validate_display_name()

	def validate_domain(self):
		active, verified = frappe.db.get_value(
			"FM Domain", self.domain_name, ["active", "verified"]
		)

		if not active:
			frappe.throw(_("Domain {0} is inactive.").format(frappe.bold(self.domain_name)))
		if not verified:
			frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(self.domain_name)))

	def validate_email(self):
		email_domain = self.email.split("@")[1]

		if email_domain != self.domain_name:
			frappe.throw(
				_("Email domain {0} does not match with domain {1}.").format(
					frappe.bold(email_domain), frappe.bold(self.domain_name)
				)
			)

	def validate_display_name(self):
		if self.is_new() and not self.display_name:
			self.display_name = frappe.get_cached_value("User", self.user, "full_name")
