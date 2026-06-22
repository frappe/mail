# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe.model.document import Document

from mail.jmap import parse_account


class JunkEmailAddress(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def before_insert(self) -> None:
		self.user = parse_account(self.account)[0]

	def validate(self) -> None:
		self.validate_duplicate_email()

	def after_insert(self) -> None:
		from mail.api.sieve import update_sieve_script_for_junk_senders

		update_sieve_script_for_junk_senders(self.account)

	def after_delete(self) -> None:
		from mail.api.sieve import update_sieve_script_for_junk_senders

		update_sieve_script_for_junk_senders(self.account)

	def validate_duplicate_email(self) -> None:
		"""Validates that the same email address is not junked multiple times for the same account."""

		if frappe.db.exists(
			"Junk Email Address",
			{"account": self.account, "email": self.email, "name": ["!=", self.name]},
		):
			frappe.throw(
				frappe._("The email address {0} is already junked for account {1}.").format(
					self.email, self.account
				)
			)


def get_junk_email_addresses(account: str) -> list[str]:
	"""Returns a list of junked email addresses for the given account."""

	return frappe.db.get_all("Junk Email Address", filters={"account": account}, pluck="email")


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Junk Email Address",
		["account", "email"],
		constraint_name="unique_account_junk_email",
	)
