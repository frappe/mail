from typing import Any

import frappe
from frappe import _
from frappe.core.doctype.user.user import _get_user_for_update_password
from frappe.core.doctype.user.user import update_password as update_frappe_password
from frappe.model.document import Document

from mail.stalwart import delete_account as delete_stalwart_account
from mail.stalwart import update_password as update_stalwart_password
from mail.utils import execute_with_logging, is_stalwart_configured
from mail.utils.user import is_jmap_configured


def create_user_settings(doc: Document, method: str | None = None) -> None:
	"""Create User Settings for the new user if not already present."""

	if not frappe.db.exists("User Settings", {"user": doc.name}):
		settings = frappe.new_doc("User Settings")
		settings.user = doc.name
		settings.insert(ignore_permissions=True, ignore_mandatory=True)


def delete_user_settings(doc: Document, method: str | None = None) -> None:
	"""Delete User Settings when the user is deleted."""

	for settings in frappe.db.get_all("User Settings", filters={"user": doc.name}, pluck="name"):
		frappe.delete_doc("User Settings", settings, ignore_permissions=True, delete_permanently=True)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_password(
	new_password: str, logout_all_sessions: int = 0, key: str | None = None, old_password: str | None = None
) -> Any:
	"""Override the default update_password whitelisted method to update the password on Stalwart server when the user updates their password."""

	frappe.flags.in_update_password = True

	if not is_stalwart_configured(raise_exception=False):
		return update_frappe_password(
			new_password=new_password,
			logout_all_sessions=logout_all_sessions,
			key=key,
			old_password=old_password,
		)

	result = _get_user_for_update_password(key, old_password)
	user = result.get("user")

	result = update_frappe_password(
		new_password=new_password, logout_all_sessions=logout_all_sessions, key=key, old_password=old_password
	)

	if user and is_jmap_configured(user):
		execute_with_logging(
			lambda: update_stalwart_password(user, new_password=new_password),
			title="Failed to update password on Stalwart server",
			with_context=False,
		)

	return result


def update_account_password(doc: Document, method: str | None = None) -> None:
	"""Updates the password on Stalwart server when the user updates their password."""

	if (
		frappe.flags.in_update_password
		or doc.flags.in_insert
		or not doc.enabled
		or not is_stalwart_configured(raise_exception=False)
		or not is_jmap_configured(doc.name)
	):
		return

	user = doc.name
	new_password = doc._User__new_password

	execute_with_logging(
		lambda: update_stalwart_password(user, new_password=new_password),
		title="Failed to update password on Stalwart server",
		with_context=False,
	)


def delete_account(doc: Document, method: str | None = None) -> None:
	if not is_stalwart_configured(raise_exception=False) or not is_jmap_configured(doc.name):
		return

	user = doc.name
	execute_with_logging(
		lambda: delete_stalwart_account(user),
		title="Failed to delete account on Stalwart server",
		with_context=False,
	)
