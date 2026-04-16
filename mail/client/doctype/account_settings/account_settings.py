# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import TYPE_CHECKING
from uuid import uuid7

import frappe
from frappe.model.document import Document
from frappe.utils import cint

from mail.jmap import (
	get_core_service,
	invalidate_jmap_connection_cache,
	invalidate_jmap_identities_cache,
	invalidate_jmap_mailboxes_cache,
	parse_account,
)

if TYPE_CHECKING:
	from mail.jmap.services.core import CoreService

from mail.utils.user import is_system_manager
from mail.utils.validation import has_permission_for_user


class AccountSettings(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	@property
	def core_service(self) -> "CoreService" | None:
		"""Return the JMAP core service for the account, or None if there is an error."""

		if self.flags.in_delete:
			return None

		try:
			return get_core_service(self.account)
		except Exception:
			frappe.msgprint(f"Error getting JMAP core service for account {self.account}")
			return None

	@property
	def has_cached_jmap_connection(self) -> int:
		"""Check if there is a cached JMAP connection for the user."""

		return cint(bool(frappe.cache.hget("jmap:connection", self.user)))

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

		list_key = f"jmap:blob:{self.account}:blob_ids"
		return len(frappe.cache.lrange(list_key, 0, -1) or [])

	@property
	def total_cached_mail_messages(self) -> int:
		"""Get the total number of cached mail messages for the account."""

		list_key = f"jmap:message:{self.account}:ids"
		return len(frappe.cache.lrange(list_key, 0, -1) or [])

	@property
	def total_cached_contact_cards(self) -> int:
		"""Get the total number of cached contact cards for the account."""

		list_key = f"jmap:contact_card:{self.account}:ids"
		return len(frappe.cache.lrange(list_key, 0, -1) or [])

	def before_insert(self) -> None:
		user, _account_id = parse_account(self.account)
		self.user = user

	@frappe.whitelist()
	def clear_cached_jmap_connection(self) -> None:
		"""Clear all cached JMAP connection for the current user."""

		if self.has_clear_cache_permission():
			invalidate_jmap_connection_cache(self.user)

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

		from mail.client.doctype.mail_message.mail_message import _get_blob_cache_key

		if not self.has_clear_cache_permission():
			return

		list_key = f"jmap:blob:{self.account}:blob_ids"

		blob_ids = frappe.cache.lrange(list_key, 0, -1) or []

		for blob_id in blob_ids:
			cache_key = _get_blob_cache_key(self.account, blob_id)
			frappe.cache.delete_value(cache_key)

		frappe.cache.delete_value(list_key)

	@frappe.whitelist()
	def clear_cached_mail_messages(self) -> None:
		"""Clear all cached mail messages for the current account."""

		from mail.client.doctype.mail_message.mail_message import _get_message_cache_key

		if not self.has_clear_cache_permission():
			return

		list_key = f"jmap:message:{self.account}:ids"

		message_ids = frappe.cache.lrange(list_key, 0, -1) or []

		for msg_id in message_ids:
			cache_key = _get_message_cache_key(self.account, msg_id)
			frappe.cache.delete_value(cache_key)

		frappe.cache.delete_value(list_key)

	@frappe.whitelist()
	def clear_cached_contact_cards(self) -> None:
		"""Clear all cached contact cards for the current account."""

		from mail.client.doctype.contact_card.contact_card import _get_contact_card_cache_key

		if not self.has_clear_cache_permission():
			return

		list_key = f"jmap:contact_card:{self.account}:ids"

		contact_card_ids = frappe.cache.lrange(list_key, 0, -1) or []

		for contact_id in contact_card_ids:
			cache_key = _get_contact_card_cache_key(self.account, contact_id)
			frappe.cache.delete_value(cache_key)

		frappe.cache.delete_value(list_key)

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
