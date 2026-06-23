# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe.model.document import Document

from mail.jmap import parse_account
from mail.utils.user import get_account_scoped_permission_query, has_account_scoped_permission


class JunkEmailAddress(Document):
	"""A junked sender, shared per JMAP account ID — every user with access to the
	account sees and manages the same junk list."""

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_duplicate_email()

	def after_insert(self) -> None:
		from mail.api.sieve import update_sieve_script_for_junk_senders

		update_sieve_script_for_junk_senders(self._full_account())

	def after_delete(self) -> None:
		from mail.api.sieve import update_sieve_script_for_junk_senders

		update_sieve_script_for_junk_senders(self._full_account())

	def _full_account(self) -> str:
		"""The `user:account_id` handle for the user acting on the shared list.

		The junk-senders sieve block lives on the account's server-side script, so
		regenerating it needs a JMAP connection — use the acting user's handle (passed via
		flags for API inserts, otherwise the session user, who must have access)."""

		return self.flags.get("account") or f"{frappe.session.user}:{self.account_id}"

	def validate_duplicate_email(self) -> None:
		"""Validates that the same email address is not junked multiple times for the same account.

		Scoped to `account_id` so a shared account can't have the same address junked twice.
		"""

		if frappe.db.exists(
			"Junk Email Address",
			{"account_id": self.account_id, "email": self.email, "name": ["!=", self.name]},
		):
			frappe.throw(
				frappe._("The email address {0} is already junked for this account.").format(self.email)
			)


def get_junk_email_addresses(account: str) -> list[str]:
	"""Returns a list of junked email addresses for the given account.

	Keyed on `account_id` so every user with access to a shared account sees the same list.
	"""

	account_id = parse_account(account)[1]
	return frappe.db.get_all("Junk Email Address", filters={"account_id": account_id}, pluck="email")


def get_permission_query_condition(user: str | None = None) -> str:
	return get_account_scoped_permission_query("Junk Email Address", user=user)


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Junk Email Address":
		return False

	return has_account_scoped_permission(doc, user=user)


def on_doctype_update() -> None:
	# Junk list is shared per account_id, so uniqueness is on (account_id, email).
	frappe.db.add_unique(
		"Junk Email Address",
		["account_id", "email"],
		constraint_name="unique_account_id_junk_email",
	)
