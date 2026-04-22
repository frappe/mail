# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BlockedEmailAddress(Document):
	def validate(self) -> None:
		self.validate_duplicate_email()

	def after_insert(self) -> None:
		from mail.api.sieve import update_sieve_script_for_blocked_emails

		update_sieve_script_for_blocked_emails(self.user)

	def after_delete(self) -> None:
		from mail.api.sieve import update_sieve_script_for_blocked_emails

		update_sieve_script_for_blocked_emails(self.user)

	def validate_duplicate_email(self) -> None:
		"""Validates that the same email address is not blocked multiple times for the same user."""

		if frappe.db.exists(
			"Blocked Email Address",
			{"user": self.user, "email": self.email, "name": ["!=", self.name]},
		):
			frappe.throw(
				frappe._("The email address {0} is already blocked for user {1}.").format(
					self.email, self.user
				)
			)


def get_blocked_email_addresses(user: str) -> list[str]:
	"""Returns a list of blocked email addresses for the given user."""

	return frappe.db.get_all("Blocked Email Address", filters={"user": user}, pluck="email")


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Blocked Email Address",
		["user", "email"],
		constraint_name="unique_user_blocked_email",
	)
