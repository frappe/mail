# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from functools import cached_property
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document

from mail.client.doctype.account_settings.account_settings import sync_account_settings
from mail.jmap import get_jmap_session_manager
from mail.jmap.connection import JMAPConnection, JMAPConnectionInfo
from mail.jmap.services.mail.identity import IdentityService
from mail.utils import get_config
from mail.utils.dt import timestamp_to_datetime
from mail.utils.user import is_system_manager


class UserSettings(Document):
	@property
	def server_url(self) -> str | None:
		"""Returns the server URL from the configuration."""

		config = get_config()
		return config.get("server_url")

	@cached_property
	def session(self) -> dict:
		"""Returns the JMAP session for the user."""

		return get_jmap_session_manager(self.user).get_session() or {}

	@property
	def session_state(self) -> str | None:
		"""Returns the state of the JMAP session for the user."""

		return self.session.get("state")

	@property
	def session_last_update(self) -> str | None:
		"""Returns the last update timestamp of the JMAP session for the user in the user's timezone."""

		timestamp = self.session.get("timestamp")
		if timestamp:
			return timestamp_to_datetime(timestamp, as_str=True)

	@property
	def jmap_session(self) -> str:
		"""Returns the JMAP session for the user as a JSON string."""

		return json.dumps(self.session, indent=4)

	@property
	def connection(self) -> JMAPConnection | None:
		"""Returns a JMAP connection for the user if the username and app password are set, otherwise returns None."""

		if self.username and self.get_password("app_password"):
			server_url = get_config("server_url")

			try:
				return JMAPConnection(
					JMAPConnectionInfo(server_url, self.username, self.get_password("app_password"))
				)
			except Exception:
				pass

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		if not self.username or frappe.flags.in_migrate:
			return

		self.validate_jmap_settings()

	def on_update(self) -> None:
		if connection := self.connection:
			sync_account_settings(self.user, connection.accounts)

	def after_delete(self) -> None:
		for settings in frappe.db.get_all("Account Settings", filters={"user": self.user}, pluck="name"):
			frappe.delete_doc("Account Settings", settings, ignore_permissions=True, delete_permanently=True)

	def validate_jmap_settings(self) -> None:
		"""Validate the JMAP settings by connecting to the JMAP server and verifying the default outgoing email."""

		if not self.username or self.flags.skip_jmap_validation:
			return

		if not self.get_password("app_password"):
			frappe.throw(_("App Password is required to validate JMAP settings."))

		connection = self.connection
		if not connection:
			frappe.throw(
				_(
					"Unable to connect to the JMAP server with the provided username and app password. Please check your settings."
				)
			)

		if self.default_outgoing_email:
			personal_account_id = next(
				(account_id for account_id, details in connection.accounts.items() if details["isPersonal"]),
				None,
			)

			if not personal_account_id:
				frappe.throw(_("No personal account found for the user on the JMAP server."))

			identity_service = IdentityService(f"{self.user}:{personal_account_id}", connection)

			if not identity_service.get_identity_id_by_email(self.default_outgoing_email):
				frappe.throw(
					_(
						"Default Outgoing Email {0} is not found in the identities of the JMAP account."
					).format(frappe.bold(self.default_outgoing_email))
				)

	@frappe.whitelist()
	def clear_jmap_session(self) -> None:
		"""Clears the JMAP session for the user."""

		get_jmap_session_manager(self.user).clear_session()

	@frappe.whitelist()
	def show_app_password(self) -> str:
		"""Returns the app password of the user."""

		frappe.only_for("Administrator")
		return self.get_password("app_password")

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
