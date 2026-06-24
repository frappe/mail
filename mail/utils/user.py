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


def is_local_user(user: str) -> bool:
	"""Returns True if the user is a local user else False."""

	if has_user_settings(user) and frappe.db.exists(
		"Principal Settings", {"principal_type": "Individual", "principal_name": user}
	):
		return True

	return False


def get_jmap_username(user: str) -> str | None:
	"""Returns the JMAP username of the user."""

	return frappe.db.get_value("User Settings", {"user": user}, "username")


@request_cache
def get_user_account_ids(user: str) -> list[str]:
	"""Returns the JMAP account IDs the user has access to.

	The IDs are read from the user's cached JMAP session (populated whenever a JMAP
	connection is established). This is the source of truth for which Account Settings
	a user may read/write, since those documents are shared per JMAP account ID.
	"""

	from mail.jmap import get_jmap_session_manager

	session = get_jmap_session_manager(user).get_session() or {}
	return list((session.get("accounts") or {}).keys())


def get_session_account(account_id: str) -> str:
	"""Rebuild the full ``user:account_id`` JMAP handle for the current session user.

	The frontend sends only the bare ``account_id``; the user component of the handle is
	always the logged-in user. Internal code keeps using the full handle as the canonical
	account identifier, so API endpoints reconstruct it here at the boundary.
	"""

	if not account_id:
		frappe.throw(_("Account ID is required."))

	return f"{frappe.session.user}:{account_id}"


def resolve_account_handle(account: str) -> str:
	"""Resolve an account reference to a full ``user:account_id`` handle.

	Accepts either a full ``user:account_id`` handle (passed positionally by internal
	callers) or a bare ``account_id`` (sent by the frontend), so dual-use whitelisted
	functions work in both contexts. Account IDs never contain a colon, so its presence
	reliably distinguishes the two forms.
	"""

	if not account:
		frappe.throw(_("Account is required."))

	return account if ":" in account else f"{frappe.session.user}:{account}"


def get_account_scoped_permission_query(
	doctype: str, column: str = "account_id", user: str | None = None
) -> str:
	"""Permission query condition for doctypes shared by JMAP account.

	Restricts non-admins to rows whose `column` (the bare JMAP account ID) is one of the
	accounts the user has access to. `column="name"` is used by doctypes named directly by
	the account ID (e.g. Account Settings).
	"""

	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	account_ids = get_user_account_ids(user)
	if not account_ids:
		return "1=0"

	ids = ", ".join(frappe.db.escape(account_id) for account_id in account_ids)
	return f"(`tab{doctype}`.`{column}` in ({ids}))"


def has_account_scoped_permission(doc, column: str = "account_id", user: str | None = None) -> bool:
	"""Document-level permission for doctypes shared by JMAP account.

	Grants access when the user is a System Manager or has JMAP access to the account the
	document is scoped to.
	"""

	user = user or frappe.session.user

	if is_system_manager(user):
		return True

	value = doc.name if column == "name" else doc.get(column)
	return value in get_user_account_ids(user)


def get_account_emails(account: str) -> list[str]:
	"""Returns the list of email addresses associated with the account."""

	from mail.jmap import get_identities

	emails = []
	for identity in get_identities(*parse_account(account)):
		emails.append(identity["email"])

	return emails


def get_user_personal_account(user: str, raise_exception: bool = False) -> str | None:
	"""Returns the personal account of the user."""

	from mail.client.doctype.user_account.user_account import fetch_user_accounts

	for account in fetch_user_accounts(user, limit=None):
		if account["is_personal"]:
			return account["name"]

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


def _get_local_principals(principal_type: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of principal names for the given principal type."""

	return frappe.db.get_all(
		"Principal Settings",
		filters={"principal_type": principal_type},
		order_by=order_by,
		pluck="principal_name",
	)


def get_local_api_keys(order_by: str = "creation desc") -> list[str]:
	"""Returns a list of API Key principals."""

	return _get_local_principals("API Key", order_by)


def get_local_domains(order_by: str = "creation desc") -> list[str]:
	"""Returns a list of Domain principals."""

	return _get_local_principals("Domain", order_by)


def get_local_groups(order_by: str = "creation desc") -> list[str]:
	"""Returns a list of Group principals."""

	return _get_local_principals("Group", order_by)


def get_local_individuals(order_by: str = "creation desc") -> list[str]:
	"""Returns a list of Individual principals."""

	return _get_local_principals("Individual", order_by)


def get_local_mailing_lists(order_by: str = "creation desc") -> list[str]:
	"""Returns a list of List principals."""

	return _get_local_principals("List", order_by)


def get_local_oauth_clients(order_by: str = "creation desc") -> list[str]:
	"""Returns a list of OAuth Client principals."""

	return _get_local_principals("OAuth Client", order_by)


def get_local_roles(order_by: str = "creation desc") -> list[str]:
	"""Returns a list of Role principals."""

	return _get_local_principals("Role", order_by)


def get_local_emails(order_by: str = "creation desc") -> list[str]:
	"""Returns a list of associated email addresses."""

	return frappe.db.get_all(
		"Principal Settings",
		filters={"principal_type": ["in", ["Group", "Individual", "List"]]},
		order_by=order_by,
		pluck="principal_name",
	)


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

	from mail.client.doctype.account_settings.account_settings import get_or_create_account_settings

	store = get_data_store(parse_account(account)[1])
	value = store.get(Entity.STATE, f"{type}_current_state")

	if not value:
		get_or_create_account_settings(account)

	return value


def update_sync_state(account: str, type: Literal["email"], state: str) -> None:
	"""Updates the Sync State for the given account and type.

	The state (and its last-update timestamp, used to throttle scheduled syncs) lives in
	the per-account data store, shared across every user of the account.
	"""

	store = get_data_store(parse_account(account)[1])

	current_state = store.get(Entity.STATE, f"{type}_current_state")
	store.set(Entity.STATE, f"{type}_previous_state", current_state)
	store.set(Entity.STATE, f"{type}_current_state", state)
	store.set(Entity.STATE, f"{type}_state_last_update", frappe.utils.now())


@reconnect_on_failure()
def clear_sync_state(account_id: str, type: Literal["email"]) -> None:
	"""Clear the Sync State for the given account ID and type."""

	store = get_data_store(account_id)
	store.delete(Entity.STATE, f"{type}_current_state")
	store.delete(Entity.STATE, f"{type}_previous_state")
	store.delete(Entity.STATE, f"{type}_state_last_update")
