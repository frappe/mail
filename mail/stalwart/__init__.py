import frappe
from frappe import _
from frappe.utils import random_string
from frappe.utils.caching import redis_cache

from mail.stalwart.account import (
	Account,
	AccountService,
	Credential,
	CredentialType,
	EmailAlias,
	PasswordCredential,
	Permissions,
	PermissionType,
	RoleType,
	StorageQuota,
	UserRoles,
)
from mail.stalwart.domain import DomainService


@redis_cache(ttl=3600)
def get_domain_by_name(
	name: str, fields: list[dict] | None = None, raise_exception: bool = True
) -> dict | None:
	"""Fetches a domain by name from the Stalwart server, selecting specific fields if provided."""

	domain_service = DomainService()
	if domains := domain_service.get_all({"name": name}, fields=fields):
		return domains[0]

	if raise_exception:
		frappe.throw(_("Domain {0} not found.").format(frappe.bold(name)))


@redis_cache(ttl=3600)
def get_account_by_name(
	name: str, fields: list[dict] | None = None, raise_exception: bool = True
) -> dict | None:
	"""Fetches an account by name from the Stalwart server, selecting specific fields if provided."""

	account_service = AccountService()
	if accounts := account_service.get_all({"name": name}, fields=fields):
		return accounts[0]

	if raise_exception:
		frappe.throw(_("Account {0} not found.").format(frappe.bold(name)))


def create_account(
	name: str,
	domain: str,
	password: str | None = None,
	description: str | None = None,
	aliases: list[str] | None = None,
	groups: list[str] | None = None,
	is_admin: bool = False,
	quota: int | None = None,
	timezone: str | None = None,
) -> None:
	"""Creates an account on the Stalwart server with the specified parameters."""

	domain_id = get_domain_by_name(domain, fields=["id"], raise_exception=True)["id"]

	email_aliases = []
	domain_ids_map = {domain: domain_id}
	for alias in aliases or []:
		if not alias:
			continue

		alias = alias.strip()

		if "@" in alias:
			alias_name, alias_domain = alias.split("@", 1)

			alias_domain_id = domain_ids_map.get(alias_domain)
			if not alias_domain_id:
				alias_domain_id = get_domain_by_name(alias_domain, fields=["id"], raise_exception=True)["id"]
				domain_ids_map[alias_domain] = alias_domain_id

			email_aliases.append(EmailAlias(name=alias_name, domain_id=alias_domain_id))

	member_group_ids = []
	for group in groups or []:
		group_id = get_account_by_name(group, fields=["id"], raise_exception=False)["id"]
		member_group_ids.append(group_id)

	password = password or random_string(12)

	roles = UserRoles(
		type=RoleType.CUSTOM if is_admin else RoleType.USER, role_ids=["d"] if is_admin else None
	)
	quotas = StorageQuota(max_disk_quota=quota) if quota else None

	account = Account(
		name=name,
		domain_id=domain_id,
		credentials=[Credential(type=CredentialType.PASSWORD, password=PasswordCredential(secret=password))],
		member_group_ids=member_group_ids,
		roles=roles,
		permissions=Permissions(type=PermissionType.INHERIT),
		quotas=quotas,
		aliases=email_aliases,
		description=description,
		timezone=timezone,
	)

	AccountService().create(account)
