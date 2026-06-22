# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import TYPE_CHECKING
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.jmap import (
	get_core_service,
	get_mailbox_id_by_role,
	invalidate_jmap_identities_cache,
	invalidate_jmap_mailboxes_cache,
	parse_account,
)
from mail.storage import get_blob_store, get_data_store
from mail.storage.data_store import Entity

if TYPE_CHECKING:
	from mail.jmap.services.core import CoreService

from mail.utils import log_error
from mail.utils.user import get_account_emails, is_system_manager
from mail.utils.validation import has_permission_for_user


class AccountSettings(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	@property
	def core_service(self) -> "CoreService" | None:
		"""Return the JMAP core service for the account, or None if there is an error."""

		if self.flags.in_delete or not self.account:
			return None

		try:
			return get_core_service(self.account)
		except Exception:
			frappe.msgprint(f"Error getting JMAP core service for account {self.account}")
			return None

	@property
	def email_current_state(self) -> str:
		"""Returns the current state of the email sync for the account, or an empty string if not set."""

		user, account_id = parse_account(self.account)
		store = get_data_store(user, account_id)
		return store.get(Entity.STATE, "email_current_state") or ""

	@property
	def email_previous_state(self) -> str:
		"""Returns the previous state of the email sync for the account, or an empty string if not set."""

		user, account_id = parse_account(self.account)
		store = get_data_store(user, account_id)
		return store.get(Entity.STATE, "email_previous_state") or ""

	@property
	def has_cached_jmap_identities(self) -> int:
		"""Check if there are cached JMAP identities for the account."""

		service = self.core_service
		if not service:
			return 0

		return cint(bool(service.cache.get("identities")))

	@property
	def has_cached_jmap_mailboxes(self) -> int:
		"""Check if there are cached JMAP mailboxes for the account."""

		service = self.core_service
		if not service:
			return 0

		return cint(bool(service.cache.get("mailboxes")))

	@property
	def total_cached_blobs(self) -> int:
		"""Get the total number of cached blobs for the account."""

		user, account_id = parse_account(self.account)
		store = get_blob_store(user, account_id)
		return store.count()

	@property
	def total_cached_mail_messages(self) -> int:
		"""Get the total number of cached mail messages for the account."""

		user, account_id = parse_account(self.account)
		store = get_data_store(user, account_id)
		return store.count(Entity.EMAIL)

	@property
	def total_cached_contact_cards(self) -> int:
		"""Get the total number of cached contact cards for the account."""

		user, account_id = parse_account(self.account)
		store = get_data_store(user, account_id)
		return store.count(Entity.CONTACT_CARD)

	def validate(self) -> None:
		self.validate_default_outgoing_email()

	def validate_default_outgoing_email(self) -> None:
		"""Keep the default outgoing email valid: fall back to the account's first identity
		when the chosen one isn't one of the account's identities."""

		if not self.default_outgoing_email or frappe.flags.in_migrate:
			return

		try:
			emails = get_account_emails(self.account)
		except Exception:
			return

		if emails and self.default_outgoing_email not in emails:
			self.default_outgoing_email = emails[0]

	def before_insert(self) -> None:
		self.user = parse_account(self.account)[0]

	def after_insert(self) -> None:
		create_archive_mailbox(self.account)

	def on_update(self) -> None:
		# Toggling screening changes the automation sieve's screening gate, so regenerate it. Skipped
		# during migrate (no JMAP round-trips) and only when the flag actually changed.
		if frappe.flags.in_migrate:
			return

		if self.has_value_changed("enable_screening"):
			from mail.api.sieve import update_sieve_script_for_screened_emails

			update_sieve_script_for_screened_emails(self.account)

	def after_delete(self) -> None:
		"""Clear all caches related to the account when the settings are deleted."""

		self.clear_cached_jmap_identities()
		self.clear_cached_jmap_mailboxes()
		self.clear_cached_mail_messages()
		self.clear_cached_contact_cards()
		self.clear_cached_blobs()

	@frappe.whitelist()
	def clear_cached_jmap_identities(self) -> None:
		"""Clear all cached JMAP identities for the current account."""

		if self.has_clear_cache_permission():
			invalidate_jmap_identities_cache(self.account)

	@frappe.whitelist()
	def clear_cached_jmap_mailboxes(self) -> None:
		"""Clear all cached JMAP mailboxes for the current account."""

		if self.has_clear_cache_permission():
			invalidate_jmap_mailboxes_cache(self.account)

	@frappe.whitelist()
	def clear_cached_blobs(self) -> None:
		"""Clear all cached JMAP blobs for the current account."""

		if not self.has_clear_cache_permission():
			return

		user, account_id = parse_account(self.account)
		store = get_blob_store(user, account_id)
		store.delete_all()

	@frappe.whitelist()
	def clear_cached_mail_messages(self) -> None:
		"""Clear all cached mail messages for the current account."""

		if not self.has_clear_cache_permission():
			return

		user, account_id = parse_account(self.account)
		store = get_data_store(user, account_id)
		store.delete_all(Entity.EMAIL)

	@frappe.whitelist()
	def clear_cached_contact_cards(self) -> None:
		"""Clear all cached contact cards for the current account."""

		if not self.has_clear_cache_permission():
			return

		user, account_id = parse_account(self.account)
		store = get_data_store(user, account_id)
		store.delete_all(Entity.CONTACT_CARD)

	def has_clear_cache_permission(self) -> bool:
		"""Check if the user has permission to clear cache."""

		return has_permission_for_user(self.user, raise_exception=True)

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


def sync_account_settings(user: str, accounts: dict[str, dict]) -> None:
	"""Sync the Account Settings doctype with the current accounts of the user."""

	existing_account_settings_map = {
		s["account"]: s["name"]
		for s in frappe.db.get_all("Account Settings", {"user": user}, ["name", "account"])
	}
	current_accounts = set([f"{user}:{account_id}" for account_id in accounts.keys()])

	accounts_to_delete = set(existing_account_settings_map.keys()) - current_accounts
	accounts_to_add = current_accounts - set(existing_account_settings_map.keys())

	for account in accounts_to_delete:
		frappe.delete_doc("Account Settings", existing_account_settings_map[account], ignore_permissions=True)

	for account in accounts_to_add:
		settings = frappe.new_doc("Account Settings")
		settings.user = user
		settings.account = account
		# Default the outgoing sender to the account's first identity.
		emails = get_account_emails(account)
		if emails:
			settings.default_outgoing_email = emails[0]
		settings.save(ignore_permissions=True)


def backfill_default_outgoing_emails() -> None:
	"""Resolve each account's default outgoing email against its identities.

	Run as a background job (e.g. after the Outgoing-settings migration), where JMAP is
	reachable — unlike during `bench migrate`. Keeps an existing default if it's one of
	the account's identities, otherwise uses the account's first identity.
	"""

	for settings in frappe.get_all("Account Settings", fields=["name", "account", "default_outgoing_email"]):
		try:
			emails = get_account_emails(settings["account"])
		except Exception:
			continue

		if not emails:
			continue

		current = settings["default_outgoing_email"]
		resolved = current if current in emails else emails[0]
		if resolved != current:
			frappe.db.set_value(
				"Account Settings",
				settings["name"],
				"default_outgoing_email",
				resolved,
				update_modified=False,
			)

	frappe.db.commit()


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	return f"(`tabAccount Settings`.user = '{user}')"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Account Settings":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True

	return doc.user == user


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Account Settings",
		["account"],
		constraint_name="unique_account_settings",
	)


def create_archive_mailbox(account: str) -> None:
	"""Create the archive mailbox for the account if it does not already exist."""

	try:
		get_mailbox_id_by_role(account, "archive", create_if_not_exists=True)

	except Exception:
		log_error(
			_("Archive Mailbox Creation Error"),
			_("Failed to create archive mailbox for account {0}").format(account),
		)
