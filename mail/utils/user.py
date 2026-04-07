from typing import Literal
from urllib.parse import urljoin

import frappe
from frappe import _
from frappe.core.doctype.user.user import generate_keys
from frappe.query_builder import Table
from frappe.utils.caching import request_cache

from mail.utils import reconnect_on_failure, user_context
from mail.utils.cache import get_cluster_for_tenant, get_tenant_for_user


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


def has_user_settings(user: str, raise_exception: bool = False) -> bool:
	"""Returns True if the user has User Settings else False."""

	if frappe.db.exists("User Settings", {"user": user}):
		return True

	if raise_exception:
		frappe.throw(_("User {0} does not have User Settings configured.").format(frappe.bold(user)))

	return False


def has_jmap_settings(user: str, raise_exception: bool = False) -> bool:
	"""Returns True if the user has JMAP settings configured else False."""

	if frappe.db.exists("User Settings", {"user": user, "username": ["!=", None]}):
		return True

	if raise_exception:
		frappe.throw(_("User {0} does not have JMAP settings configured.").format(frappe.bold(user)))

	return False


def is_tenant_bound_user(user: str) -> bool:
	"""Returns True if the user is a tenant bound user else False."""

	return bool(get_tenant_for_user(user))


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


def get_account_for_user(user: str) -> str | None:
	"""Returns the account of the user."""

	return frappe.db.get_value("User Settings", user, "username")


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


def get_tenant_for_domain(domain_name: str) -> str | None:
	"""Returns the tenant for the domain."""

	return get_principal_tenant(domain_name, raise_exception=False)


@frappe.whitelist()
def get_user_tenant() -> str | None:
	"""Returns the tenant of the user."""

	return get_tenant_for_user(frappe.session.user)


def get_principals_tenant_map(principal_names: list[str]) -> dict[str, str]:
	"""Returns a mapping of principal names to their associated tenants."""

	bindings = frappe.db.get_all(
		"Mail Principal Binding",
		{"principal_name": ["in", principal_names]},
		["principal_name", "tenant"],
	)

	return {b.principal_name: b.tenant for b in bindings}


def _get_tenant_principals(tenant: str, principal_type: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of principals of the given type for the given tenant."""

	return frappe.db.get_all(
		"Mail Principal Binding",
		filters={"tenant": tenant, "principal_type": principal_type},
		order_by=order_by,
		pluck="principal_name",
	)


def get_tenant_api_keys(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of API Key principals for the given tenant."""

	return _get_tenant_principals(tenant, "API Key", order_by)


def get_tenant_domains(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of domain principals for the given tenant."""

	return _get_tenant_principals(tenant, "Domain", order_by)


def get_tenant_groups(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of group principals for the given tenant."""

	return _get_tenant_principals(tenant, "Group", order_by)


def get_tenant_individuals(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of individual principals for the given tenant."""

	return _get_tenant_principals(tenant, "Individual", order_by)


def get_tenant_mailing_lists(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of list principals for the given tenant."""

	return _get_tenant_principals(tenant, "List", order_by)


def get_tenant_oauth_clients(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of OAuth Client principals for the given tenant."""

	return _get_tenant_principals(tenant, "OAuth Client", order_by)


def get_tenant_roles(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of Role principals for the given tenant."""

	return _get_tenant_principals(tenant, "Role", order_by)


def get_tenant_emails(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of email addresses associated with the given tenant."""

	return frappe.db.get_all(
		"Mail Principal Binding",
		filters={"tenant": tenant, "principal_type": ["in", ["Group", "Individual", "List"]]},
		order_by=order_by,
		pluck="principal_name",
	)


def get_principal_tenant(principal_name: str, raise_exception: bool = True) -> str | None:
	"""Returns the tenant associated with the given principal name."""

	if tenant := frappe.db.get_value("Mail Principal Binding", {"principal_name": principal_name}, "tenant"):
		return tenant

	if raise_exception:
		frappe.throw(
			_("No Mail Principal Binding found for principal name: {0}").format(frappe.bold(principal_name))
		)


def get_caldav_settings(user: str) -> dict:
	"""Returns the CalDAV settings for the user."""

	caldav_settings = {}

	user_settings = frappe.get_doc("User Settings", user)
	if user_settings.server_url and user_settings.username and user_settings.app_password:
		cluster = get_cluster_for_tenant(get_tenant_for_user(user))
		base_url = frappe.db.get_value("Mail Cluster", cluster, "base_url")
		caldav_url = urljoin(base_url, ".well-known/caldav")

		caldav_settings.update(
			{
				"url": caldav_url,
				"auth": (
					user_settings.username,
					user_settings.get_password("app_password"),
				),
			}
		)

	return caldav_settings


def get_sync_state(user: str, type: Literal["email"]) -> str | None:
	"""Returns the Sync State for the given user and type."""

	return frappe.db.get_value("User Settings", user, f"{type}_current_state")


@frappe.whitelist(methods=["POST"])
def generate_user_keys(user: str) -> dict:
	"""Generates API and Secret keys for the user."""

	session_user = frappe.session.user
	if is_system_manager(session_user) or session_user == user:
		with user_context("Administrator"):
			return generate_keys(user)

	frappe.throw(_("Not permitted"), frappe.PermissionError)


def update_sync_state(user: str, type: Literal["email"], state: str) -> None:
	"""Updates the Sync State for the given user and type."""

	state_last_update = f"{type}_state_last_update"
	previous_state = f"{type}_previous_state"
	current_state = f"{type}_current_state"

	USER_SETTINGS = frappe.qb.DocType("User Settings")
	(
		frappe.qb.update(USER_SETTINGS)
		.set(getattr(USER_SETTINGS, state_last_update), frappe.utils.now())
		.set(getattr(USER_SETTINGS, previous_state), getattr(USER_SETTINGS, current_state))
		.set(getattr(USER_SETTINGS, current_state), state)
		.where(USER_SETTINGS.user == user)
	).run()


@reconnect_on_failure()
def clear_sync_state(user: str, type: Literal["email"]) -> None:
	"""Clear the Sync State for the given user and type."""

	frappe.db.set_value("User Settings", user, f"{type}_current_state", None, update_modified=False)
