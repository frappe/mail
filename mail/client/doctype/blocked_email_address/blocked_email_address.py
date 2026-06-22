# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe.model.document import Document

from mail.jmap import parse_account


class BlockedEmailAddress(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def before_insert(self) -> None:
		# `account` is the "user:account_id" handle; `user` records who blocked, while `account_id`
		# is the shared key so a group account's block list is the same for everyone with access.
		user, account_id = parse_account(self.account)
		self.user = user
		self.account_id = account_id

	def validate(self) -> None:
		self.validate_duplicate_email()

	def after_insert(self) -> None:
		from mail.api.sieve import update_sieve_script_for_blocked_emails

		update_sieve_script_for_blocked_emails(self.account)

	def after_delete(self) -> None:
		from mail.api.sieve import update_sieve_script_for_blocked_emails

		update_sieve_script_for_blocked_emails(self.account)

	def validate_duplicate_email(self) -> None:
		"""Validates that the same email address is not blocked multiple times for the same account.

		Scoped to `account_id` (not the per-user `account` handle) so a shared account can't have the
		same address blocked twice by different users.
		"""

		if frappe.db.exists(
			"Blocked Email Address",
			{"account_id": self.account_id, "email": self.email, "name": ["!=", self.name]},
		):
			frappe.throw(
				frappe._("The email address {0} is already blocked for this account.").format(self.email)
			)


def get_blocked_email_addresses(account: str) -> list[str]:
	"""Returns the blocked email addresses for the given account.

	Keyed on `account_id` so every user with access to a shared account sees the same list.
	"""

	account_id = parse_account(account)[1]
	return frappe.db.get_all("Blocked Email Address", filters={"account_id": account_id}, pluck="email")


def on_doctype_update() -> None:
	# Block list is shared per account_id, so uniqueness is on (account_id, email).
	frappe.db.add_unique(
		"Blocked Email Address",
		["account_id", "email"],
		constraint_name="unique_account_id_blocked_email",
	)
