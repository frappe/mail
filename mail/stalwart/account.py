import json
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

import frappe
from frappe import _
from frappe.utils import random_string

from mail.stalwart.cli import StalwartCLI
from mail.utils import snake_to_camel


class CredentialType(Enum):
	PASSWORD = "Password"


@dataclass
class PasswordCredential:
	secret: str


def _default_password_credential() -> PasswordCredential:
	return PasswordCredential(secret=random_string(20))


def _default_credentials() -> list["Credential"]:
	return [Credential()]


@dataclass
class Credential:
	type: CredentialType = CredentialType.PASSWORD
	password: PasswordCredential = field(default_factory=_default_password_credential)

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
class CustomRoles:
	role_ids: list[str] = field(default_factory=list)


@dataclass
class UserRoles:
	type: RoleType = RoleType.USER
	roles: CustomRoles | None = None

	def __post_init__(self) -> None:
		if self.type == RoleType.CUSTOM and not self.roles:
			raise ValueError("Custom role type requires roles to be defined.")

		if self.type != RoleType.CUSTOM and self.roles:
			raise ValueError("Only custom role type can have roles defined.")

	def to_dict(self) -> dict:
		if self.type == RoleType.CUSTOM:
			return {"@type": self.type.value, "roleIds": {role_id: True for role_id in self.roles.role_ids}}
		else:
			return {"@type": self.type.value}


class PermissionType(Enum):
	INHERIT = "Inherit"
	MERGE = "Merge"
	REPLACE = "Replace"


@dataclass
class PermissionsList:
	enabled_permissions: list[str] | None = None
	disabled_permissions: list[str] | None = None


@dataclass
class Permissions:
	type: PermissionType = PermissionType.INHERIT
	permissions: PermissionsList | None = None

	def __post_init__(self) -> None:
		if self.type == PermissionType.INHERIT and (
			self.permissions
			and (self.permissions.enabled_permissions or self.permissions.disabled_permissions)
		):
			raise ValueError(
				"Inherit permission type should not have enabled or disabled permissions defined."
			)

		if self.type != PermissionType.INHERIT and not (
			self.permissions
			and (self.permissions.enabled_permissions or self.permissions.disabled_permissions)
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
				"enabledPermissions": {perm: True for perm in self.permissions.enabled_permissions}
				if self.permissions and self.permissions.enabled_permissions
				else {},
				"disabledPermissions": {perm: True for perm in self.permissions.disabled_permissions}
				if self.permissions and self.permissions.disabled_permissions
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
			if value is not None:
				quotas[snake_to_camel(field_name)] = value

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
	type: EncryptionType = EncryptionType.DISABLED
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
	credentials: list[Credential] = field(default_factory=_default_credentials)
	member_group_ids: list[str] | None = None
	roles: UserRoles = field(default_factory=UserRoles)
	permissions: Permissions = field(default_factory=Permissions)
	quotas: StorageQuota = field(default_factory=StorageQuota)
	aliases: list[EmailAlias] | None = None
	description: str | None = None
	locale: str = "en_US"
	timezone: str | None = None
	encryption_at_rest: EncryptionAtRest = field(default_factory=EncryptionAtRest)

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
	DEFAULT_FIELDS: ClassVar[list[str]] = [
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
	ALLOWED_FILTER_KEYS: ClassVar[set[str]] = {"text", "name", "domainId", "memberGroupIds"}

	@classmethod
	def _resolved_fields(cls, fields: list[str] | None) -> list[str]:
		return fields if isinstance(fields, list) else cls.DEFAULT_FIELDS

	@classmethod
	def _append_filters(cls, commands: list[str], filters: dict[str, str]) -> None:
		for key, value in filters.items():
			if key in cls.ALLOWED_FILTER_KEYS:
				commands.extend(["--where", f"{key}={value}"])
			else:
				frappe.throw(
					_("Invalid filter key: {0}. Allowed keys are: {1}").format(
						key, ", ".join(cls.ALLOWED_FILTER_KEYS)
					)
				)

	@staticmethod
	def _parse_query_output(output: str) -> list[dict]:
		if not output:
			return []

		return [json.loads(account) for account in output.splitlines()]

	def get(self, id: str, fields: list[str] | None = None) -> dict:
		"""Fetches an account by ID from the Stalwart server, selecting specific fields if provided."""

		fields = self._resolved_fields(fields)

		commands = ["get", "Account", id]

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			if response["output"]:
				return json.loads(response["output"])
			else:
				frappe.throw(title=_("Account not found"), msg=_("Account with ID {0} not found.").format(id))
		else:
			frappe.throw(title=_("Failed to fetch account"), msg=response["output"] or response["error"])

	def get_all(self, filters: dict[str, str] | None = None, fields: list[str] | None = None) -> list[dict]:
		"""Fetches all accounts from the Stalwart server, applying optional filters and selecting specific fields."""

		filters = filters or {}
		fields = self._resolved_fields(fields)

		commands = ["query", "Account"]

		if filters:
			self._append_filters(commands, filters)

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			return self._parse_query_output(response["output"])
		else:
			frappe.throw(title=_("Failed to fetch accounts"), msg=response["output"] or response["error"])

	def create(self, account: "Account") -> None:
		"""Creates a new account on the Stalwart server with the provided account data."""

		account_data = account.to_dict()
		account_json = json.dumps(account_data)
		response = self.run(["create", "Account", "--json", account_json])

		if not response["success"]:
			frappe.throw(title=_("Failed to create account"), msg=response["output"] or response["error"])

	def delete(self, ids: list[str]) -> None:
		"""Deletes accounts with the specified IDs from the Stalwart server."""

		if not ids:
			frappe.throw(title=_("No account IDs provided"), msg=_("No account IDs provided for deletion."))

		response = self.run(["delete", "Account", "--ids", ",".join(ids)])

		if not response["success"]:
			frappe.throw(title=_("Failed to delete accounts"), msg=response["output"] or response["error"])

	def update_password(self, id: str, new_password: str) -> None:
		"""Updates the password for the specified account on the Stalwart server."""

		if not new_password:
			frappe.throw(title=_("Invalid password"), msg=_("New password cannot be empty."))

		credentials = self.get(id, fields=["credentials"]).get("credentials", {})

		row_id = "0"
		if credentials:
			for idx, credential in credentials.items():
				if credential["@type"] == CredentialType.PASSWORD.value:
					row_id = str(idx)
					break

		response = self.run(
			["update", "Account", id, "--field", f"credentials/{row_id}/secret={new_password}"]
		)

		if not response["success"]:
			frappe.throw(
				title=_("Failed to update password for account {0}").format(id),
				msg=response["output"] or response["error"],
			)
