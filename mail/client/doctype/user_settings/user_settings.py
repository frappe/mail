# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from datetime import UTC, datetime
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document

from mail.jmap.connection import JMAPConnection, JMAPConnectionInfo
from mail.jmap.services.mail.identity import IdentityService
from mail.storage import get_data_store
from mail.utils import get_mail_config
from mail.utils.dt import parse_iso_datetime
from mail.utils.user import is_local_user, is_system_manager


class UserSettings(Document):
	@property
	def session_state(self) -> str | None:
		"""Returns the current JMAP session state for the user from the data store."""

		store = get_data_store(self.user)
		return store.get("states", "session_state")

	@property
	def session_last_update(self) -> str | None:
		"""Returns the last update time of the JMAP session state for the user from the data store."""

		store = get_data_store(self.user)
		value = store.get("states", "session_last_update")

		if value:
			return parse_iso_datetime(value)

	def autoname(self) -> None:
		self.name = str(uuid7())

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

			store = get_data_store(self.user)
			store.set_many(
				"states",
				{
					"session_state": connection.state,
					"session_last_update": datetime.now(UTC).isoformat(),
				},
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

		existing_account_settings_map = {
			s["account"]: s["name"]
			for s in frappe.db.get_all("Account Settings", {"user": self.user}, ["name", "account"])
		}
		current_accounts = set([f"{self.user}:{account_id}" for account_id in connection.accounts.keys()])

		accounts_to_delete = set(existing_account_settings_map.keys()) - current_accounts
		accounts_to_add = current_accounts - set(existing_account_settings_map.keys())

		for account in accounts_to_delete:
			frappe.delete_doc(
				"Account Settings", existing_account_settings_map[account], ignore_permissions=True
			)

		for account in accounts_to_add:
			settings = frappe.new_doc("Account Settings")
			settings.user = self.user
			settings.account = account
			settings.save(ignore_permissions=True)

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
