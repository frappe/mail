# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from pypika.terms import ExistsCriterion
from frappe.model.document import Document


class FMMailbox(Document):
	def validate(self) -> None:
		self.validate_email()
		self.validate_domain()
		self.validate_display_name()

	def validate_email(self) -> None:
		email_domain = self.email.split("@")[1]

		if email_domain != self.domain_name:
			frappe.throw(
				_("Email domain {0} does not match with domain {1}.").format(
					frappe.bold(email_domain), frappe.bold(self.domain_name)
				)
			)

	def validate_domain(self) -> None:
		enabled, verified = frappe.db.get_value(
			"FM Domain", self.domain_name, ["enabled", "verified"]
		)

		if not enabled:
			frappe.throw(_("Domain {0} is disabled.").format(frappe.bold(self.domain_name)))
		if not verified:
			frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(self.domain_name)))

	def validate_display_name(self) -> None:
		if self.is_new() and not self.display_name:
			self.display_name = frappe.db.get_value("User", self.user, "full_name")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_user(doctype, txt, searchfield, start, page_len, filters) -> list:
	domain_name = filters.get("domain_name")

	if not domain_name:
		return []

	USER = frappe.qb.DocType("User")
	MAILBOX = frappe.qb.DocType("FM Mailbox")

	return (
		frappe.qb.from_(USER)
		.select(USER.name)
		.where(
			(USER.enabled == 1)
			& (USER[searchfield].like(f"%{txt}%"))
			& (USER.name.like(f"%@{domain_name}"))
			& ExistsCriterion(
				frappe.qb.from_(MAILBOX).select(MAILBOX.name).where(MAILBOX.name == USER.name)
			).negate()
		)
		.limit(page_len)
	).run(as_dict=False)
