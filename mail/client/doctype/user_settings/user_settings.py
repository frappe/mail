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
from mail.utils.user import is_local_user, is_system_manager


class UserSettings(Document):
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

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		if not self.username or frappe.flags.in_migrate:
			return

		self.validate_jmap_settings()
		self.validate_local_user()

	def validate_jmap_settings(self) -> None:
		"""Validate the JMAP settings by connecting to the JMAP server and verifying the default outgoing email."""

		if not self.username or self.flags.skip_jmap_validation:
			return

		server_url = self.server_url or get_config("server_url")

		if not server_url or not self.get_password("app_password"):
			frappe.throw(_("Server URL and App Password are required to validate JMAP settings."))

		try:
			connection = JMAPConnection(
				JMAPConnectionInfo(server_url, self.username, self.get_password("app_password"))
			)
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

		sync_account_settings(self.user, connection.accounts)

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
