# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.jmap import (
	get_core_service,
	invalidate_jmap_connection_cache,
	invalidate_jmap_identities_cache,
	invalidate_jmap_mailboxes_cache,
)
from mail.jmap.connection import JMAPConnection, JMAPConnectionInfo
from mail.jmap.services.mail.identity import IdentityService
from mail.utils import get_mail_config
from mail.utils.user import is_local_user, is_system_manager
from mail.utils.validation import has_permission_for_user


class UserSettings(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	@property
	def has_cached_jmap_connection(self) -> int:
		"""Check if there is a cached JMAP connection for the user."""

		return cint(bool(frappe.cache.hget("jmap:connection", self.user)))

	@property
	def has_cached_jmap_identities(self) -> int:
		"""Check if there are cached JMAP identities for the user."""

		if not self.username or self.flags.in_delete:
			return 0

		service = get_core_service(self.user)
		return cint(bool(service.cache.get("identities")))

	@property
	def has_cached_jmap_mailboxes(self) -> int:
		"""Check if there are cached JMAP mailboxes for the user."""

		if not self.username or self.flags.in_delete:
			return 0

		service = get_core_service(self.user)
		return cint(bool(service.cache.get("mailboxes")))

	@property
	def total_cached_blobs(self) -> int:
		"""Get the total number of cached blobs for the user."""

		list_key = f"jmap:blob:{self.user}:blob_ids"
		return len(frappe.cache.lrange(list_key, 0, -1) or [])

	@property
	def total_cached_mail_messages(self) -> int:
		"""Get the total number of cached mail messages for the user."""

		list_key = f"jmap:message:{self.user}:ids"
		return len(frappe.cache.lrange(list_key, 0, -1) or [])

	@property
	def total_cached_contact_cards(self) -> int:
		"""Get the total number of cached contact cards for the user."""

		list_key = f"jmap:contact_card:{self.user}:ids"
		return len(frappe.cache.lrange(list_key, 0, -1) or [])

	def validate(self) -> None:
		if not self.username or frappe.flags.in_migrate:
			return

		self.validate_jmap_settings()
		self.validate_local_user()

	def validate_jmap_settings(self) -> None:
		"""Validate the JMAP settings by connecting to the JMAP server and verifying the default outgoing email."""

		if self.flags.skip_jmap_validation:
			return

		if not self.username:
			return

		server_url = self.server_url or get_mail_config("server_url")

		if not server_url or not self.get_password("app_password"):
			frappe.throw(_("Server URL and App Password are required to validate JMAP settings."))

		try:
			info = JMAPConnectionInfo(server_url, self.username, self.get_password("app_password"))
			connection = JMAPConnection(info)
		except Exception as e:
			if (
				hasattr(e, "response")
				and hasattr(e.response, "status_code")
				and e.response.status_code == 401
			):
				frappe.throw(_("Unable to connect to the JMAP server. Please check your credentials."))

			frappe.throw(
				_(
					"Unable to connect to the JMAP server. Please check the server URL and your network connection."
				)
			)

		if self.default_outgoing_email:
			identity_service = IdentityService(self.user, connection)

			if not identity_service.get_identity_id_by_email(self.default_outgoing_email):
				frappe.throw(
					_(
						"Default Outgoing Email {0} is not found in the identities of the JMAP account."
					).format(frappe.bold(self.default_outgoing_email))
				)

	def validate_local_user(self) -> None:
		"""Validate that if the user is local, then the JMAP username must be the same as the User name and a Principal Settings must exist for the user."""

		if not is_local_user(self.user):
			return

		if self.username != self.user:
			frappe.throw(_("JMAP Username must be the same as the User name."))

		if not frappe.db.exists(
			"Principal Settings",
			{"principal_name": self.username},
			"principal_name",
		):
			frappe.throw(
				_(
					"Principal Settings for {0} does not exist. Please create Principal Settings with the principal name same as the JMAP username."
				).format(frappe.bold(self.username))
			)

	@frappe.whitelist()
	def show_app_password(self) -> str:
		"""Returns the app password of the user."""

		frappe.only_for("Administrator")
		return self.get_password("app_password")

	@frappe.whitelist()
	def clear_cached_jmap_connection(self) -> None:
		"""Clear all cached JMAP connection for the current user."""

		if self.has_clear_cache_permission():
			invalidate_jmap_connection_cache(self.user)

	@frappe.whitelist()
	def clear_cached_jmap_identities(self) -> None:
		"""Clear all cached JMAP identities for the current user."""

		if self.has_clear_cache_permission():
			invalidate_jmap_identities_cache(self.user)

	@frappe.whitelist()
	def clear_cached_jmap_mailboxes(self) -> None:
		"""Clear all cached JMAP mailboxes for the current user."""

		if self.has_clear_cache_permission():
			invalidate_jmap_mailboxes_cache(self.user)

	@frappe.whitelist()
	def clear_cached_blobs(self) -> None:
		"""Clear all cached JMAP blobs for the current user."""

		from mail.client.doctype.mail_message.mail_message import _get_blob_cache_key

		if not self.has_clear_cache_permission():
			return

		user = self.user
		list_key = f"jmap:blob:{user}:blob_ids"

		blob_ids = frappe.cache.lrange(list_key, 0, -1) or []

		for blob_id in blob_ids:
			cache_key = _get_blob_cache_key(user, blob_id)
			frappe.cache.delete_value(cache_key)

		frappe.cache.delete_value(list_key)

	@frappe.whitelist()
	def clear_cached_mail_messages(self) -> None:
		"""Clear all cached mail messages for the current user."""

		from mail.client.doctype.mail_message.mail_message import _get_message_cache_key

		if not self.has_clear_cache_permission():
			return

		user = self.user
		list_key = f"jmap:message:{user}:ids"

		message_ids = frappe.cache.lrange(list_key, 0, -1) or []

		for msg_id in message_ids:
			cache_key = _get_message_cache_key(user, msg_id)
			frappe.cache.delete_value(cache_key)

		frappe.cache.delete_value(list_key)

	@frappe.whitelist()
	def clear_cached_contact_cards(self) -> None:
		"""Clear all cached contact cards for the current user."""

		from mail.client.doctype.contact_card.contact_card import _get_contact_card_cache_key

		if not self.has_clear_cache_permission():
			return

		user = self.user
		list_key = f"jmap:contact_card:{user}:ids"

		contact_card_ids = frappe.cache.lrange(list_key, 0, -1) or []

		for contact_id in contact_card_ids:
			cache_key = _get_contact_card_cache_key(user, contact_id)
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

	return f"(`tabUser Settings`.user = '{user}')"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "User Settings":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True

	return doc.user == user
