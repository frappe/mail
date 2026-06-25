# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe.model.document import Document

from mail.jmap import parse_account
from mail.utils.user import (
	get_account_scoped_permission_query,
	get_session_account,
	has_account_scoped_permission,
)

# Screening actions: what happens to future mail from a screened sender.
REJECT = "Reject"  # discard the incoming mail silently
SPAM = "Spam"  # file the incoming mail into the Spam (Junk) folder


class ScreenedEmailAddress(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_duplicate_email()

	def on_update(self) -> None:
		from mail.api.sieve import maybe_build_automation_sieve

		# Runs on both insert and save. `email` is set_only_once, so on an edit only the action can
		# change; regenerate on insert (no prior doc) and whenever the action is changed (e.g. switching
		# Spam <-> Reject in Desk), since that moves the sender between sieve blocks. Skipped when a
		# caller paused builds for a bulk write (it rebuilds once at the end instead).
		if self.has_value_changed("action"):
			maybe_build_automation_sieve(get_session_account(self.account_id))

	def after_delete(self) -> None:
		from mail.api.sieve import maybe_build_automation_sieve

		maybe_build_automation_sieve(get_session_account(self.account_id))

	def validate_duplicate_email(self) -> None:
		"""Validates that the same email address is not screened more than once for the same account.

		Scoped to `account_id` (not the per-user `account` handle) so a shared account can't have the
		same address screened twice by different users. Uniqueness is on the address alone, not the
		action, so a sender always has exactly one screening rule (Reject or Spam, never both).
		"""

		if frappe.db.exists(
			"Screened Email Address",
			{"account_id": self.account_id, "email": self.email, "name": ["!=", self.name]},
		):
			frappe.throw(
				frappe._("The email address {0} is already screened for this account.").format(self.email)
			)


def get_screened_email_addresses(account: str, action: str | None = None) -> list[dict]:
	"""Returns the screened email addresses (with their action) for the given account.

	Keyed on `account_id` so every user with access to a shared account sees the same list. Pass
	`action` to restrict to a single action (e.g. only the Reject rules).
	"""

	account_id = parse_account(account)[1]
	filters = {"account_id": account_id}
	if action:
		filters["action"] = action

	return frappe.db.get_all("Screened Email Address", filters=filters, fields=["email", "action"])


def get_permission_query_condition(user: str | None = None) -> str:
	return get_account_scoped_permission_query("Screened Email Address", user=user)


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Screened Email Address":
		return False

	return has_account_scoped_permission(doc, user=user)


def on_doctype_update() -> None:
	# Screening list is shared per account_id, so uniqueness is on (account_id, email) — one rule
	# per address regardless of action.
	frappe.db.add_unique(
		"Screened Email Address",
		["account_id", "email"],
		constraint_name="unique_account_id_screened_email",
	)
