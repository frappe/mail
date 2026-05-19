from typing import Literal

import frappe
from frappe import _
from frappe.core.doctype.user.user import generate_keys
from frappe.query_builder import Table
from frappe.utils.caching import request_cache

from mail.jmap.services.core import parse_account
from mail.storage import get_data_store
from mail.storage.data_store import Entity
from mail.utils import reconnect_on_failure, user_context


def is_administrator(user: str) -> bool:
	"""Returns True if the user is Administrator else False."""

	return user == "Administrator"


@request_cache
def has_role(user: str, roles: str | list) -> bool:
	"""Returns True if the user has any of the given roles else False."""

	if isinstance(roles, str):
		roles = [roles]

	user_roles = frappe.get_roles(user)
	for role in roles:
		if role in user_roles:
			return True

	return False


@request_cache
def is_system_manager(user: str) -> bool:
	"""Returns True if the user is Administrator or System Manager else False."""

	return is_administrator(user) or has_role(user, "System Manager")


@request_cache
def is_mail_admin(user: str) -> bool:
	"""Returns True if the user is a Mail Admin else False."""

	return has_role(user, "Mail Admin")


def has_user_settings(user: str, raise_exception: bool = False) -> bool:
	"""Returns True if the user has User Settings else False."""

	if frappe.db.exists("User Settings", {"user": user}):
		return True

	if raise_exception:
		frappe.throw(_("User {0} does not have User Settings configured.").format(frappe.bold(user)))

	return False


def is_jmap_configured(user: str, raise_exception: bool = False) -> bool:
	"""Returns True if the user has JMAP settings configured else False."""

	if frappe.db.exists("User Settings", {"user": user, "username": ["!=", None]}):
		return True

	if raise_exception:
		frappe.throw(_("User {0} does not have JMAP settings configured.").format(frappe.bold(user)))

	return False


def get_jmap_username(user: str) -> str | None:
	"""Returns the JMAP username of the user."""

	return frappe.db.get_value("User Settings", {"user": user}, "username")


def get_account_emails(account: str) -> list[str]:
	"""Returns the list of email addresses associated with the account."""

	from mail.jmap import get_identities

	emails = []
	for identity in get_identities(account):
		emails.append(identity["email"])

	return emails


def get_user_personal_account(
	user: str, property: str | None = None, raise_exception: bool = False
) -> str | None:
	"""Returns the personal account of the user."""

	from mail.client.doctype.user_account.user_account import fetch_user_accounts

	for account in fetch_user_accounts(user, limit=None):
		if account["is_personal"]:
			return account[property or "name"]

	if raise_exception:
		frappe.throw(_("User {0} does not have a personal account configured.").format(frappe.bold(user)))


def get_user_emails(user: str) -> list[str]:
	"""Returns the list of email addresses associated with the user."""

	emails = []

	from mail.client.doctype.user_account.user_account import fetch_user_accounts

	for account in [a["name"] for a in fetch_user_accounts(user, limit=None)]:
		emails.extend(get_account_emails(account))

	return emails


def get_user_hashed_password(user: str) -> str | None:
	"""Returns the hashed password for a given user."""

	Auth = Table("__Auth")
	result = (
		frappe.qb.from_(Auth)
		.select(Auth.password)
		.where(
			(Auth.doctype == "User")
			& (Auth.name == user)
			& (Auth.fieldname == "password")
			& (Auth.encrypted == 0)
		)
		.limit(1)
		.run()
	)
	if result:
		return result[0][0]


def get_user_email_address(user: str) -> str | None:
	"""Returns the primary email address of the user."""

	return frappe.db.get_value("User", user, "email")


@frappe.whitelist(methods=["POST"])
def generate_user_keys(user: str) -> dict:
	"""Generates API and Secret keys for the user."""

	session_user = frappe.session.user
	if is_system_manager(session_user) or session_user == user:
		with user_context("Administrator"):
			return generate_keys(user)

	frappe.throw(_("Not permitted"), frappe.PermissionError)


def get_sync_state(account: str, type: Literal["email"]) -> str | None:
	"""Returns the Sync State for the given account and type."""

	user, account_id = parse_account(account)
	store = get_data_store(user, account_id)
	value = store.get(Entity.STATE, f"{type}_current_state")

	if not value and not frappe.db.exists("Account Settings", {"account": account}):
		settings = frappe.new_doc("Account Settings")
		settings.account = account
		settings.flags.ignore_links = True
		settings.insert(ignore_permissions=True)

	return value


def update_sync_state(account: str, type: Literal["email"], state: str) -> None:
	"""Updates the Sync State for the given account and type."""

	user, account_id = parse_account(account)
	store = get_data_store(user, account_id)

	current_state = store.get(Entity.STATE, f"{type}_current_state")
	store.set(Entity.STATE, f"{type}_previous_state", current_state)
	store.set(Entity.STATE, f"{type}_current_state", state)

	state_last_update_field = f"{type}_state_last_update"
	ACCOUNT_SETTINGS = frappe.qb.DocType("Account Settings")
	(
		frappe.qb.update(ACCOUNT_SETTINGS)
		.set(getattr(ACCOUNT_SETTINGS, state_last_update_field), frappe.utils.now())
		.where(ACCOUNT_SETTINGS.account == account)
	).run()


@reconnect_on_failure()
def clear_sync_state(account: str, type: Literal["email"]) -> None:
	"""Clear the Sync State for the given account and type."""

	user, account_id = parse_account(account)
	store = get_data_store(user, account_id)
	store.delete(Entity.STATE, f"{type}_current_state")
	store.delete(Entity.STATE, f"{type}_previous_state")
