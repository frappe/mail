# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe.model.document import Document


class BlockedEmailAddress(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_duplicate_email()

	def after_insert(self) -> None:
		from mail.api.sieve import update_sieve_script_for_blocked_emails

		update_sieve_script_for_blocked_emails(self.account)

	def after_delete(self) -> None:
		from mail.api.sieve import update_sieve_script_for_blocked_emails

		update_sieve_script_for_blocked_emails(self.account)

	def validate_duplicate_email(self) -> None:
		"""Validates that the same email address is not blocked multiple times for the same account."""

		if frappe.db.exists(
			"Blocked Email Address",
			{"account": self.account, "email": self.email, "name": ["!=", self.name]},
		):
			frappe.throw(
				frappe._("The email address {0} is already blocked for account {1}.").format(
					self.email, self.account
				)
			)


def get_blocked_email_addresses(account: str) -> list[str]:
	"""Returns a list of blocked email addresses for the given account."""

	return frappe.db.get_all("Blocked Email Address", filters={"account": account}, pluck="email")


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Blocked Email Address",
		["account", "email"],
		constraint_name="unique_account_blocked_email",
	)
