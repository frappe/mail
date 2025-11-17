# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SyncState(Document):
	pass


def create_sync_state(account: str) -> "SyncState":
	"""Create a new Sync State document for the given account."""

	doc = frappe.new_doc("Sync State")
	doc.account = account
	doc.insert(ignore_permissions=True, ignore_if_duplicate=True)

	return doc


def clear_sync_state(account: str) -> None:
	"""Clear the Sync State for the given account."""

	frappe.db.set_value("Sync State", account, "current_state", None)


def get_current_state(account: str) -> str | None:
	"""Returns the current state for the given account."""

	return frappe.db.get_value("Sync State", account, "current_state")


def update_current_state(account: str, state: str) -> None:
	"""Updates the current state for the given account."""

	JSS = frappe.qb.DocType("Sync State")
	(
		frappe.qb.update(JSS)
		.set(JSS.last_synced_at, frappe.utils.now())
		.set(JSS.previous_state, JSS.current_state)
		.set(JSS.current_state, state)
		.where(JSS.account == account)
	).run()
