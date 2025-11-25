from typing import Literal
from urllib.parse import urljoin

import frappe
from frappe import _
from frappe.core.doctype.user.user import generate_keys
from frappe.query_builder import Table
from frappe.utils.caching import request_cache

from mail.utils import user_context
from mail.utils.cache import get_account_for_user, get_aliases_for_user, get_tenant_for_user


def is_administrator(user: str) -> bool:
	"""Returns True if the user is Administrator else False."""

	return user == "Administrator"


@request_cache
def is_system_manager(user: str) -> bool:
	"""Returns True if the user is Administrator or System Manager else False."""

	return is_administrator(user) or has_role(user, "System Manager")


def get_user_email_addresses(user: str) -> list:
	"""Returns the list of email addresses associated with the user."""

	email_addresses = []
	if account := get_account_for_user(user):
		email_addresses.append(account)
	if aliases := get_aliases_for_user(user):
		email_addresses.extend(aliases)

	return email_addresses


def get_account_email_addresses(account: str) -> list:
	"""Returns the list of email addresses associated with the account."""

	user = frappe.db.get_value("Mail Account", account, "user")
	return get_user_email_addresses(user)


def get_user_linked_domains(user: str) -> list:
	"""Returns the list of linked domains associated with the user."""

	linked_domains = set()
	if email_addresses := get_user_email_addresses(user):
		for email_address in email_addresses:
			linked_domains.add(email_address.split("@")[1])

	return list(linked_domains)


@frappe.whitelist()
def get_user_tenant() -> str | None:
	"""Returns the tenant of the user."""

	return get_tenant_for_user(frappe.session.user)


@request_cache
def is_tenant_owner(tenant: str, user: str) -> bool:
	"""Returns True if the user is the owner of the tenant else False."""

	return frappe.db.get_value("Mail Tenant", tenant, "user") == user


@request_cache
def is_tenant_admin(tenant: str, user: str) -> bool:
	"""Returns True if the user is an admin of the tenant else False."""

	return has_role(user, "Mail Admin") and frappe.db.exists(
		"Mail Tenant Member", {"tenant": tenant, "user": user, "is_admin": 1}
	)


@request_cache
def is_tenant_member(tenant: str, user: str) -> bool:
	"""Returns True if the user is a member of the tenant else False."""

	return frappe.db.exists("Mail Tenant Member", {"tenant": tenant, "user": user})


@request_cache
def is_account_owner(account: str, user: str) -> bool:
	"""Returns True if the account is associated with the user else False."""

	return frappe.db.get_value("Mail Account", account, "user") == user


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


@frappe.whitelist(methods=["POST"])
def generate_user_keys(user: str) -> dict:
	"""Generates API and Secret keys for the user."""

	session_user = frappe.session.user
	if is_system_manager(session_user) or session_user == user:
		with user_context("Administrator"):
			return generate_keys(user)

	frappe.throw(_("Not permitted"), frappe.PermissionError)


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


def get_caldav_settings(user: str) -> dict:
	"""Returns the CalDAV settings for the user."""

	caldav_settings = {}

	if account := get_account_for_user(user):
		account = frappe.get_doc("Mail Account", account)
		cluster = frappe.db.get_value("Mail Tenant", account.tenant, "cluster")
		base_url = frappe.db.get_value("Mail Cluster", cluster, "base_url")
		caldav_url = urljoin(base_url, ".well-known/caldav")

		caldav_settings.update(
			{"url": caldav_url, "auth": (account.email, account.get_account_app_password())}
		)

	return caldav_settings


def get_sync_state(user: str, type: Literal["email"]) -> str | None:
	"""Returns the Sync State for the given user and type."""

	return frappe.db.get_value("User", user, f"jmap_{type}_current_state")


def update_sync_state(user: str, type: Literal["email"], state: str) -> None:
	"""Updates the Sync State for the given user and type."""

	state_last_update = f"jmap_{type}_state_last_update"
	previous_state = f"jmap_{type}_previous_state"
	current_state = f"jmap_{type}_current_state"

	USER = frappe.qb.DocType("User")
	(
		frappe.qb.update(USER)
		.set(getattr(USER, state_last_update), frappe.utils.now())
		.set(getattr(USER, previous_state), getattr(USER, current_state))
		.set(getattr(USER, current_state), state)
		.where(USER.name == user)
	).run()


def clear_sync_state(user: str, type: Literal["email"]) -> None:
	"""Clear the Sync State for the given user and type."""

	frappe.db.set_value("User", user, f"jmap_{type}_current_state", None, update_modified=False)
