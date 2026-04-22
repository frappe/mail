# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BlockedEmailAddress(Document):
	pass


def get_blocked_email_addresses(user: str) -> list[str]:
	"""Returns a list of blocked email addresses for the given user."""

	return frappe.db.get_all("Blocked Email Address", filters={"user": user}, pluck="email")


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Blocked Email Address",
		["user", "email"],
		constraint_name="unique_user_blocked_email",
	)
