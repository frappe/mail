# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import base64
from datetime import datetime, timezone
from email.utils import parseaddr
from functools import cached_property
from urllib.parse import urljoin

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now, validate_email_address
from frappe.utils.data import convert_utc_to_system_timezone, get_datetime

from mail.backend import MailBackendAccountManager, get_mail_backend_api
from mail.client.doctype.identity.identity import _add_identity as add_identity
from mail.client.doctype.push_subscription.push_subscription import create_push_subscriptions
from mail.jmap import get_jmap_client, invalidate_jmap_cache, invalidate_jmap_client_cache, raise_for_status
from mail.utils import (
	convert_html_to_text,
	generate_random_phrase,
	hash_password,
	normalize_email,
)
from mail.utils.cache import (
	get_aliases_for_user,
	get_cluster_for_tenant,
	get_tenant_for_domain,
	get_tenant_for_user,
)
from mail.utils.dt import convert_to_utc
from mail.utils.user import get_user_hashed_password, has_role, is_system_manager, is_tenant_admin
from mail.utils.validation import (
	has_permission_for_account,
	is_email_assigned,
	is_subaddressed_email,
	is_valid_email_for_domain,
	validate_domain_is_verified,
	validate_domain_owned_by_tenant,
)


class MailAccount(Document):
	@cached_property
	def _account(self) -> dict:
		"""Fetches the account details from the backend API."""

		if not self.is_new() and self.enabled:
			try:
				backend_api = get_mail_backend_api("Mail Cluster", get_cluster_for_tenant(self.tenant))
				response = backend_api.request(method="GET", endpoint=f"/api/principal/{self.email}")

				_response_json = response.json()
				if response.status_code == 200:
					return _response_json["data"]
				else:
					frappe.throw(title=_("Failed to fetch Account Details"), msg=str(_response_json))
			except Exception:
				frappe.log_error(
					title=_("Failed to fetch Account Details"),
					message=frappe.get_traceback(with_context=True),
				)

		return {}

	@property
	def _disk_quota(self) -> int:
		"""Returns the disk quota in bytes."""

		return self._account.get("quota", 0)

	@property
	def _used_quota(self) -> int:
		"""Returns the used quota in bytes."""

		return self._account.get("usedQuota", 0)

	@property
	def disk_quota(self) -> float:
		"""Returns the disk quota in gigabytes."""

		return self._disk_quota / (1024**3) if self._disk_quota else 0

	@property
	def used_quota(self) -> float:
		"""Returns the used quota in gigabytes."""

		return self._used_quota / (1024**3) if self._used_quota else 0

	@property
	def quota_usage(self) -> float:
		"""Returns the quota usage percentage."""

		return (self.used_quota / self.disk_quota) * 100 if self.disk_quota else 0

	def autoname(self) -> None:
		self.email = self.email.strip().lower()
		self.name = self.email

	def before_validate(self) -> None:
		self.set_tenant()

	def validate(self) -> None:
		self.validate_enabled()
		self.validate_domain()
		self.validate_user()
		self.validate_user_tenant()
		self.validate_tenant_max_accounts()
		self.validate_email()
		self.set_normalized_email()
		self.validate_app_password()
		self.validate_secret_hash()
		self.validate_default_outgoing_email()
		self.validate_display_name()
		self.validate_reply_to()
		self.validate_backup_email()

	def on_update(self) -> None:
		self.clear_cache()

		if self.enabled:
			if self.has_value_changed("enabled") or self.has_value_changed("email"):
				quota = cint(frappe.db.get_value("Mail Domain", self.domain_name, "default_disk_quota")) or 10
				request = MailBackendAccountManager(
					"Mail Cluster", get_cluster_for_tenant(self.tenant)
				).create(
					self.email,
					self.display_name,
					cint(quota * (1024**3)),
					self.secret_hash,
				)
				if request.status != "Completed":
					frappe.throw(
						_("Failed to create account {0} on the mail server.").format(frappe.bold(self.email)),
						title=_("Account Creation Failed"),
					)
			elif self.has_value_changed("display_name") or self.has_value_changed("secret_hash"):
				MailBackendAccountManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).update(
					self.email,
					self.display_name,
					self.secret_hash,
					self.get_doc_before_save().secret_hash,
				)

				if self.has_value_changed("secret_hash"):
					self.invalidate_jmap_cache()
		elif self.has_value_changed("enabled"):
			MailBackendAccountManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).delete(self.email)

	def on_trash(self) -> None:
		self.clear_cache()

		if self.enabled:
			MailBackendAccountManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).delete(self.email)

	def set_tenant(self) -> None:
		"""Sets the tenant based on the domain."""

		if not self.tenant:
			self.tenant = get_tenant_for_domain(self.domain_name)

	def validate_enabled(self) -> None:
		"""Validates the enabled field."""

		if self.enabled:
			return

		if alias := frappe.db.exists(
			"Mail Alias", {"enabled": 1, "alias_for_type": self.doctype, "alias_for_name": self.name}
		):
			frappe.throw(
				_("The account is linked to Mail Alias {0}. Please disable it first.").format(
					frappe.bold(alias)
				)
			)

		if frappe.db.exists("Mailing List Member", {"member_type": self.doctype, "member_name": self.name}):
			frappe.throw(_("The account is linked to a Mailing List as a member. Please remove it first."))

	def validate_domain(self) -> None:
		"""Validates the domain."""

		validate_domain_owned_by_tenant(self.domain_name, self.tenant)
		validate_domain_is_verified(self.domain_name)

	def validate_user(self) -> None:
		"""Validates the user."""

		if not has_role(self.user, "Mail User"):
			frappe.throw(_("User {0} does not have Mail User role.").format(frappe.bold(self.user)))

	def validate_user_tenant(self) -> None:
		"""Validates the user tenant."""

		if self.is_new() or self.enabled:
			if self.tenant != get_tenant_for_user(self.user):
				frappe.throw(
					_("Domain {0} and User {1} must belong to the same tenant.").format(
						frappe.bold(self.domain_name), frappe.bold(self.user)
					)
				)

	def validate_tenant_max_accounts(self) -> None:
		"""Validates the Tenant Max Accounts."""

		total_accounts = frappe.db.count("Mail Account", filters={"tenant": self.tenant, "enabled": 1})
		max_accounts = frappe.db.get_value("Mail Tenant", self.tenant, "max_accounts")
		if total_accounts >= max_accounts:
			frappe.throw(
				_("You have reached the maximum limit of {0} accounts for the tenant.").format(
					frappe.bold(max_accounts)
				)
			)

	def validate_email(self) -> None:
		"""Validates the email address."""

		if not self.email:
			frappe.throw(_("Email is mandatory."))
		is_subaddressed_email(self.email, raise_exception=True)
		is_email_assigned(self.email, self.doctype, raise_exception=True)
		is_valid_email_for_domain(self.email, self.domain_name, raise_exception=True)

	def set_normalized_email(self) -> None:
		"""Sets the normalized email."""

		if not self.normalized_email:
			self.normalized_email = normalize_email(self.email)

	def validate_app_password(self) -> None:
		"""Validates the app password."""

		if self.is_new() or self.app_password:
			return

		frappe.throw(_("App Password is mandatory."))

	def validate_secret_hash(self) -> None:
		"""Validates the secret hash."""

		if not self.secret_hash:
			self.secret_hash = get_user_hashed_password(self.user)

			if not self.secret_hash:
				frappe.throw(_("Could not fetch password for user {0}.").format(frappe.bold(self.user)))

	def validate_default_outgoing_email(self) -> None:
		"""Validates the default outgoing email."""

		if not self.default_outgoing_email:
			self.default_outgoing_email = self.email
		else:
			if self.default_outgoing_email not in [self.email] + get_aliases_for_user(self.user):
				frappe.throw(_("Default Email must be one of the email addresses assigned to the user."))

	def validate_display_name(self) -> None:
		"""Validates the display name."""

		if self.is_new() and not self.display_name:
			self.display_name = frappe.db.get_value("User", self.user, "full_name")

	def validate_reply_to(self) -> None:
		"""Validates the reply-to addresses."""

		if not self.reply_to:
			return

		reply_to = {}
		for rt in self.reply_to.split(","):
			rt = rt.strip()
			display_name, email = parseaddr(rt)

			if not email:
				frappe.throw(_("Invalid reply-to address: {0}").format(frappe.bold(rt)))

			reply_to[email] = display_name

		self.reply_to = ", ".join([f"{display_name} <{email}>" for email, display_name in reply_to.items()])

	def validate_backup_email(self) -> None:
		"""Validates the backup email."""

		validate_email_address(self.backup_email, True)

	def clear_cache(self) -> None:
		"""Clears the Cache."""

		frappe.cache.hdel(f"user|{self.user}", ["account", "default_outgoing_email"])
		frappe.cache.hdel(f"email|{self.email}", "account")

	@frappe.whitelist()
	def get_account_app_password(self) -> str:
		"""Returns the app password for the Mail Account."""

		has_permission_for_account(self.name)
		return self._get_account_app_password()

	@frappe.whitelist()
	def invalidate_jmap_cache(self) -> None:
		"""Invalidates JMAP cache for the Mail Account."""

		invalidate_jmap_cache(self.name)

	@frappe.whitelist()
	def sync_jmap_identities(self) -> None:
		"""Syncs JMAP identities for the Mail Account."""

		frappe.only_for("System Manager")
		self._sync_jmap_identities()

	@frappe.whitelist()
	def set_quota(self, quota: int) -> None:
		"""Sets the quota for the Mail Account."""

		user = frappe.session.user
		if not is_system_manager(user) and not is_tenant_admin(self.tenant, user):
			frappe.throw(_("You do not have permission to set quota for this account."))
		elif not self.enabled:
			frappe.throw(_("Cannot set quota for a disabled account."))
		elif quota < 0:
			frappe.throw(_("Quota cannot be negative."))

		MailBackendAccountManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).set_quota(
			self.email, quota
		)
		frappe.msgprint(_("A job has been queued to set the quota."), alert=True, indicator="blue")

	@frappe.whitelist()
	def regenerate_app_password(self, account_password: str) -> None:
		"""Regenerates the app password for the Mail Account."""

		has_permission_for_account(self.name)
		self._generate_app_password(account_password, save=True)

		frappe.msgprint(_("App Password has been regenerated."), alert=True, indicator="green")

	def _get_account_app_password(self) -> str:
		"""Returns the app password for the Mail Account."""

		if self.app_password:
			if app_password := self.get_password("app_password"):
				return app_password

		frappe.throw(_("App Password is not set for the account {0}.").format(frappe.bold(self.name)))

	def _generate_app_password(self, account_password: str, save: bool = True) -> None:
		"""Generates a app password for the Mail Account."""

		if not account_password:
			frappe.throw(_("Account password is required to generate app password."))

		self.app_password = generate_random_phrase()
		base_url = frappe.db.get_value("Mail Cluster", get_cluster_for_tenant(self.tenant), "base_url")

		try:
			data = [
				{
					"type": "addAppPassword",
					"name": base64.b64encode(
						f"{frappe.local.site}${datetime.now(timezone.utc).isoformat(timespec='milliseconds')}".encode()
					).decode(),
					"password": hash_password(self.app_password),
				}
			]
			response = requests.post(
				urljoin(base_url, "api/account/auth"), json=data, auth=(self.email, account_password)
			)
			raise_for_status(response)

			if save:
				self.save()

			invalidate_jmap_client_cache(self.name)
		except Exception:
			frappe.log_error(
				title=_("Failed to generate app password"),
				message=frappe.get_traceback(with_context=True),
			)
			frappe.throw(_("Failed to generate app password. Please check your account password."))

	def _sync_jmap_identities(self) -> None:
		"""Syncs JMAP identities for the Mail Account."""

		identities = frappe.db.get_all("Identity", {"user": self.user})
		identities_emails_map = {identity["email"]: identity["name"] for identity in identities}
		identities_emails = set(identities_emails_map.keys())

		aliases = frappe.db.get_all(
			"Mail Alias",
			{"enabled": 1, "alias_for_type": "Mail Account", "alias_for_name": self.name},
			pluck="email",
		)
		user_emails = {self.email, *aliases}

		identities_to_remove = identities_emails - user_emails
		identities_to_add = user_emails - identities_emails

		for email in identities_to_remove:
			identity_name = identities_emails_map[email]
			frappe.delete_doc("Identity", identity_name)

		for email in identities_to_add:
			add_identity(self.user, email)

		self.invalidate_jmap_cache()

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


def _create_user_for_mail_account(
	email: str,
	first_name: str,
	last_name: str | None = None,
	password: str | None = None,
	is_admin: bool = False,
) -> str:
	"""Creates a User for Mail Account"""

	if frappe.db.exists("User", {"email": email}):
		frappe.throw(_("User with email {0} already exists.").format(frappe.bold(email)))

	roles = ["Mail User"]
	if is_admin:
		roles.append("Mail Admin")

	return create_user(email, first_name, last_name, password, roles)


def create_user(
	email: str,
	first_name: str,
	last_name: str | None = None,
	password: str | None = None,
	roles: list[str] | None = None,
) -> str:
	"""Creates a User document"""

	user = frappe.new_doc("User")
	user.first_name = first_name
	user.last_name = last_name
	user.username = email
	user.email = email
	user.owner = email
	user.send_welcome_email = 0
	if roles:
		user.append_roles(*roles)
	if password:
		user.new_password = password
	user.insert(ignore_permissions=True)

	return user.name


def _add_user_to_tenant(tenant: str, user: str, is_admin: bool) -> None:
	"""Adds a User to a Tenant"""

	tenant = frappe.get_doc("Mail Tenant", tenant)
	tenant.add_member(user, is_admin)


def create_mail_account(
	tenant: str,
	email: str,
	backup_email: str,
	first_name: str,
	last_name: str,
	password: str,
	is_admin: bool = False,
) -> "MailAccount":
	"""Creates a Mail Account"""

	if frappe.db.exists("Mail Account", email):
		frappe.throw(_("Mail Account {0} already exists.").format(frappe.bold(email)))

	if not password:
		frappe.throw(_("Password is required to create account."))

	user = _create_user_for_mail_account(email, first_name, last_name, password, is_admin)
	_add_user_to_tenant(tenant, user, is_admin)
	account = frappe.new_doc("Mail Account")
	account.domain_name = email.split("@")[1]
	account.user = user
	account.backup_email = backup_email
	account.insert(ignore_permissions=True)
	account._generate_app_password(account_password=password)
	create_push_subscriptions(account.name)

	return account


def sync_jmap_identities(account: str) -> None:
	"""Sync JMAP identities for the given mail account."""

	if not frappe.db.exists("Mail Account", account):
		return

	doc = frappe.get_doc("Mail Account", account)
	doc._sync_jmap_identities()


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Account":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True

	if is_tenant_admin(doc.tenant, user):
		return True

	if has_role(user, "Mail User"):
		return user == doc.user

	return False


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	if has_role(user, "Mail Admin"):
		if tenant := get_tenant_for_user(user):
			return f"(`tabMail Account`.`tenant` = {frappe.db.escape(tenant)})"

	if has_role(user, "Mail User"):
		return f"(`tabMail Account`.`user` = {frappe.db.escape(user)})"

	return "1=0"
