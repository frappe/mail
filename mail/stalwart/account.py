import json
from dataclasses import dataclass
from enum import Enum

import frappe
from frappe import _
from frappe.utils import random_string

from mail.stalwart.cli import StalwartCLI
from mail.stalwart.domain import DomainService


class CredentialType(Enum):
	PASSWORD = "Password"


@dataclass
class PasswordCredential:
	secret: str


@dataclass
class Credential:
	type: CredentialType
	password: PasswordCredential

	def to_dict(self) -> dict:
		if self.type == CredentialType.PASSWORD:
			return {
				"@type": self.type.value,
				"secret": self.password.secret,
			}
		else:
			raise ValueError(f"Unsupported credential type: {self.type}")


class RoleType(Enum):
	USER = "User"
	ADMIN = "Admin"
	CUSTOM = "Custom"


@dataclass
class UserRoles:
	type: RoleType
	role_ids: list[str] | None = None

	def __post_init__(self) -> None:
		if self.type == RoleType.CUSTOM and not self.role_ids:
			raise ValueError("Custom role type requires role_ids to be provided.")

		if self.type != RoleType.CUSTOM and self.role_ids:
			raise ValueError("Only custom role type can have role_ids defined.")

	def to_dict(self) -> dict:
		if self.type == RoleType.CUSTOM:
			return {"@type": self.type.value, "roleIds": {role_id: True for role_id in self.role_ids}}
		else:
			return {"@type": self.type.value}


class PermissionType(Enum):
	INHERIT = "Inherit"
	MERGE = "Merge"
	REPLACE = "Replace"


@dataclass
class Permissions:
	type: PermissionType
	enabled_permissions: list[str] | None = None
	disabled_permissions: list[str] | None = None

	def __post_init__(self) -> None:
		if self.type == PermissionType.INHERIT and (self.enabled_permissions or self.disabled_permissions):
			raise ValueError(
				"Inherit permission type should not have enabled or disabled permissions defined."
			)

		if self.type != PermissionType.INHERIT and not (
			self.enabled_permissions or self.disabled_permissions
		):
			raise ValueError(
				"Merge or Replace permission type requires at least one of enabled or disabled permissions to be defined."
			)

	def to_dict(self) -> dict:
		if self.type == PermissionType.INHERIT:
			return {"@type": self.type.value}
		else:
			return {
				"@type": self.type.value,
				"enabledPermissions": {perm: True for perm in self.enabled_permissions}
				if self.enabled_permissions
				else {},
				"disabledPermissions": {perm: True for perm in self.disabled_permissions}
				if self.disabled_permissions
				else {},
			}


@dataclass
class StorageQuota:
	max_emails: int | None = None
	max_mailboxes: int | None = None
	max_email_submissions: int | None = None
	max_email_identities: int | None = None
	max_participant_identities: int | None = None
	max_sieve_scripts: int | None = None
	max_push_subscriptions: int | None = None
	max_calendars: int | None = None
	max_calendar_events: int | None = None
	max_calendar_event_notifications: int | None = None
	max_address_books: int | None = None
	max_contact_cards: int | None = None
	max_files: int | None = None
	max_folders: int | None = None
	max_masked_addresses: int | None = None
	max_app_passwords: int | None = None
	max_api_keys: int | None = None
	max_public_keys: int | None = None
	max_disk_quota: int | None = None

	def __post_init__(self) -> None:
		for field_name, value in self.__dict__.items():
			if value is not None and value < 0:
				raise ValueError(f"{field_name} cannot be negative")

	def to_dict(self) -> dict:
		quotas = {}
		for field_name, value in self.__dict__.items():
			if value:
				quotas[field_name] = value

		return quotas


@dataclass
class EmailAlias:
	name: str
	domain_id: str
	enabled: bool = True
	description: str | None = None

	def to_dict(self) -> dict:
		return {
			"name": self.name,
			"domainId": self.domain_id,
			"enabled": self.enabled,
			"description": self.description,
		}


class EncryptionType(Enum):
	DISABLED = "Disabled"
	AES128 = "Aes128"
	AES256 = "Aes256"


@dataclass
class EncryptionSettings:
	public_key_id: str
	encrypt_on_append: bool = False
	allow_spam_training: bool = False

	def to_dict(self) -> dict:
		return {
			"publicKey": self.public_key_id,
			"encryptOnAppend": self.encrypt_on_append,
			"allowSpamTraining": self.allow_spam_training,
		}


@dataclass
class EncryptionAtRest:
	type: EncryptionType
	settings: EncryptionSettings | None = None

	def __post_init__(self) -> None:
		if self.type != EncryptionType.DISABLED and not self.settings:
			raise ValueError("Encryption settings must be provided when encryption is enabled.")

		if self.type == EncryptionType.DISABLED and self.settings:
			raise ValueError("Encryption settings should not be provided when encryption is disabled.")

	def to_dict(self) -> dict:
		if self.type == EncryptionType.DISABLED:
			return {"@type": self.type.value}
		else:
			return {"@type": self.type.value, "settings": self.settings.to_dict()}


@dataclass
class Account:
	name: str
	domain_id: str
	credentials: list[Credential] | None = None
	member_group_ids: list[str] | None = None
	roles: UserRoles | None = None
	permissions: Permissions | None = None
	quotas: StorageQuota | None = None
	aliases: list[EmailAlias] | None = None
	description: str | None = None
	locale: str = "en_US"
	timezone: str | None = None
	encryption_at_rest: EncryptionAtRest | None = None

	def __post_init__(self) -> None:
		self.encryption_at_rest = self.encryption_at_rest or EncryptionAtRest(type=EncryptionType.DISABLED)

	def to_dict(self) -> dict:
		return {
			"@type": "User",
			"name": self.name,
			"domainId": self.domain_id,
			"credentials": {f"{idx}": credential.to_dict() for idx, credential in enumerate(self.credentials)}
			if self.credentials
			else {},
			"memberGroupIds": {group_id: True for group_id in self.member_group_ids}
			if self.member_group_ids
			else {},
			"roles": self.roles.to_dict() if self.roles else {},
			"permissions": self.permissions.to_dict() if self.permissions else {},
			"quotas": self.quotas.to_dict() if self.quotas else {},
			"aliases": {f"{idx}": alias.to_dict() for idx, alias in enumerate(self.aliases)}
			if self.aliases
			else {},
			"description": self.description,
			"locale": self.locale,
			"timeZone": self.timezone,
			"encryptionAtRest": self.encryption_at_rest.to_dict(),
		}


class AccountService(StalwartCLI):
	def get(self, id: str, fields: list[str] | None = None) -> dict:
		"""Fetches an account by ID from the Stalwart server, selecting specific fields if provided."""

		if not isinstance(fields, list):
			fields = [
				"@type",
				"id",
				"name",
				"description",
				"emailAddress",
				"aliases",
				"domainId",
				"memberGroupIds",
				"quotas",
				"roles",
				"timeZone",
				"usedDiskQuota",
			]

		commands = commands = ["get", "account", id]

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			if response["output"]:
				return json.loads(response["output"])
			else:
				frappe.throw(_("Account with ID {0} not found.").format(id))
		else:
			frappe.throw(_("Failed to fetch account: {0}").format(response["error"]))

	def get_all(self, filters: dict[str, str] | None = None, fields: list[str] | None = None) -> list[dict]:
		"""Fetches all accounts from the Stalwart server, applying optional filters and selecting specific fields."""

		filters = filters or {}

		if not isinstance(fields, list):
			fields = [
				"@type",
				"id",
				"name",
				"description",
				"emailAddress",
				"aliases",
				"domainId",
				"memberGroupIds",
				"quotas",
				"roles",
				"timeZone",
				"usedDiskQuota",
			]

		commands = commands = ["query", "account"]

		if filters:
			allowed_filter_keys = {"text", "name", "domainId", "memberGroupIds"}
			for key, value in filters.items():
				if key in allowed_filter_keys:
					commands.extend(["--where", f"{key}={value}"])
				else:
					frappe.throw(
						_("Invalid filter key: {0}. Allowed keys are: {1}").format(
							key, ", ".join(allowed_filter_keys)
						)
					)

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			if response["output"]:
				accounts = response["output"].splitlines()
				return [json.loads(account) for account in accounts]

			return []
		else:
			frappe.throw(_("Failed to fetch accounts: {0}").format(response["error"]))

	def create(self, account: "Account") -> dict:
		account_data = account.to_dict()
		account_json = json.dumps(account_data)
		response = self.run(["create", "account", "--json", account_json])

		if not response["success"]:
			frappe.throw(_("Failed to create account: {0}").format(response["error"]))

		return response


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
	domain_manager = DomainService()
	account_manager = AccountService()

	domain_id = None
	if domains := domain_manager.get_all({"name": domain}, fields=["id"]):
		domain_id = domains[0]["id"]

	if not domain_id:
		frappe.throw(_("Domain {0} not found.").format(domain))

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
				if domains := domain_manager.get_all({"name": alias_domain}, fields=["id"]):
					alias_domain_id = domains[0]["id"]

				if not alias_domain_id:
					frappe.throw(_("Domain {0} not found for alias {1}.").format(alias_domain, alias))

				domain_ids_map[alias_domain] = alias_domain_id

			email_aliases.append(EmailAlias(name=alias_name, domain_id=alias_domain_id))

	member_group_ids = []
	for group in groups or []:
		if groups := account_manager.get_all({"name": group}, fields=["id"]):
			group_id = groups[0]["id"]
			member_group_ids.append(group_id)
		else:
			frappe.throw(_("Group {0} not found.").format(group))

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

	account_manager.create(account)
