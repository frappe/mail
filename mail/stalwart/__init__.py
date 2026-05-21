import frappe
from frappe import _
from frappe.utils import random_string
from frappe.utils.caching import redis_cache

from mail.stalwart.account import (
	Account,
	AccountService,
	Credential,
	CustomRoles,
	EmailAlias,
	PasswordCredential,
	RoleType,
	StorageQuota,
	UserRoles,
)
from mail.stalwart.app_password import AppPassword, AppPasswordService
from mail.stalwart.domain import Domain, DomainService
from mail.stalwart.role import RoleService
from mail.utils import get_config
from mail.utils.dt import utcnow
from mail.utils.user import get_user_personal_account


def _resolve_alias(alias: str) -> tuple[str, str]:
	"""Resolves alias into local-part and domain from a complete email address."""

	alias = alias.strip()
	if not alias or "@" not in alias:
		frappe.throw(_("Alias must be a complete email address: {0}").format(alias))

	alias_name, alias_domain = alias.split("@", 1)
	if not alias_name or not alias_domain:
		frappe.throw(_("Alias must be a complete email address: {0}").format(alias))

	return alias_name, alias_domain


def _resolve_group_ids(groups: list[str] | None = None) -> list[str]:
	"""Resolves account names in groups to account IDs with validation."""

	group_ids = []
	for group in groups or []:
		group_account = get_account_by_name(group, raise_exception=False)
		if not group_account:
			frappe.throw(_("Group account {0} not found on server.").format(group))

		group_ids.append(group_account["id"])

	return group_ids


@redis_cache(ttl=3600)
def get_domain_by_name(
	name: str, fields: list[str] | None = None, raise_exception: bool = True
) -> dict | None:
	"""Fetches a domain by name from the Stalwart server, selecting specific fields if provided."""

	domain_service = DomainService()
	if domains := domain_service.get_all({"name": name}, fields=fields or ["id"]):
		return domains[0]

	if raise_exception:
		frappe.throw(_("Domain {0} not found.").format(name))


@redis_cache(ttl=60)
def get_domains() -> list[dict]:
	"""Fetches all domains from the Stalwart server, selecting specific fields if provided."""

	return DomainService().get_all(
		{}, fields=["id", "name", "description", "isEnabled", "createdAt", "dnsZoneFile"]
	)


@redis_cache(ttl=3600)
def get_account_by_name(
	name: str, fields: list[str] | None = None, raise_exception: bool = True
) -> dict | None:
	"""Fetches an account by name from the Stalwart server, selecting specific fields if provided."""

	account_service = AccountService()
	if accounts := account_service.get_all({"name": name}, fields=fields or ["id"]):
		return accounts[0]

	if raise_exception:
		frappe.throw(_("Account {0} not found.").format(name))


@redis_cache(ttl=3600)
def get_role_by_description(
	description: str, fields: list[str] | None = None, raise_exception: bool = True
) -> dict | None:
	"""Fetches a role by description from the Stalwart server, selecting specific fields if provided."""

	role_service = RoleService()
	if roles := role_service.get_all({"description": description}, fields=fields or ["id"]):
		# Assuming description is unique and returning the first match.
		return roles[0]

	if raise_exception:
		frappe.throw(_("Role with description {0} not found.").format(description))


@redis_cache(ttl=3600)
def get_roles(description: str | None = None, fields: list[str] | None = None) -> list[dict]:
	"""Fetches roles from the Stalwart server, filtering by description if provided, and selecting specific fields if provided."""

	filters = {}
	if description:
		filters["description"] = description

	role_service = RoleService()
	return role_service.get_all(filters, fields=fields or ["id", "description"])


def create_domain(name: str, description: str | None = None) -> str:
	"""Creates a new domain on the Stalwart server with the specified name and description, returning the new domain's ID."""

	domain = Domain(
		name=name,
		description=description,
	)
	domain_id = DomainService().create(domain)

	get_domain_by_name.clear_cache()
	get_domains.clear_cache()

	return domain_id


def delete_domain(domain_id: str) -> None:
	"""Deletes a domain from the Stalwart server by ID."""

	DomainService().delete([domain_id])
	get_domain_by_name.clear_cache()
	get_domains.clear_cache()


def create_account(
	name: str,
	domain: str,
	password: str | None = None,
	description: str | None = None,
	aliases: list[str] | None = None,
	groups: list[str] | None = None,
	roles: list[str] | None = None,
	quota: int | None = None,
	timezone: str | None = None,
) -> None:
	"""Creates an account on the Stalwart server with the specified parameters."""

	domain_id = get_domain_by_name(domain, raise_exception=True)["id"]
	password = password or random_string(12)

	email_aliases = []
	domain_ids_map = {domain: domain_id}
	for alias in aliases or []:
		if not alias:
			continue

		alias_name, alias_domain = _resolve_alias(alias)

		alias_domain_id = domain_ids_map.get(alias_domain)
		if not alias_domain_id:
			alias_domain_id = get_domain_by_name(alias_domain, raise_exception=True)["id"]
			domain_ids_map[alias_domain] = alias_domain_id

		email_aliases.append(EmailAlias(name=alias_name, domain_id=alias_domain_id))

	member_group_ids = _resolve_group_ids(groups)

	user_roles = UserRoles(type=RoleType.USER)
	if roles:
		role_ids = []
		server_roles_map = {r["description"]: r["id"] for r in get_roles()}

		for role in roles:
			role_id = server_roles_map.get(role)
			if not role_id:
				frappe.throw(_("Role {0} does not exist on the server.").format(role))

			role_ids.append(role_id)

		if role_ids:
			user_roles = UserRoles(type=RoleType.CUSTOM, roles=CustomRoles(role_ids=role_ids))

	quotas = StorageQuota(max_disk_quota=quota) if quota is not None else None

	account = Account(
		name=name,
		domain_id=domain_id,
		credentials=[Credential(password=PasswordCredential(secret=password))],
		member_group_ids=member_group_ids,
		roles=user_roles,
		quotas=quotas,
		aliases=email_aliases,
		description=description,
		timezone=timezone,
	)

	AccountService().create(account)


def create_app_password(username: str, password: str, description: str | None = None) -> str:
	"""Creates an app password for the specified account on Stalwart and returns the secret."""

	server_url = get_config("server_url")
	description = description or f"App Password for {frappe.local.site} - {utcnow()}"

	return AppPasswordService(
		credentials={"server_url": server_url, "username": username, "password": password}
	).create(AppPassword(description=description))


def update_password(user: str | None = None, new_password: str | None = None) -> None:
	"""Updates the password for the specified user's personal account on the Stalwart server."""

	if not user:
		frappe.throw(_("User is required to update password on Stalwart server."))
	if not new_password:
		frappe.throw(_("New password is required to update password on Stalwart server."))

	account_id = get_user_personal_account(user, "id", raise_exception=False)
	AccountService().update_password(account_id, new_password)


def delete_account(user: str) -> None:
	"""Deletes the personal account of the specified user from the Stalwart server."""

	account_id = get_user_personal_account(user, "id", raise_exception=False)
	AccountService().delete([account_id])
