# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from mail.jmap.connection import JMAPConnection, JMAPConnectionInfo
from mail.jmap.services.mail.identity import IdentityService
from mail.utils.user import get_tenant_for_user, has_role, is_system_manager, is_tenant_bound_user


class UserSettings(Document):
	def validate(self) -> None:
		self.validate_jmap_settings()
		self.validate_tenant_bound_user()

	def validate_jmap_settings(self) -> None:
		"""Validate the JMAP settings by connecting to the JMAP server and verifying the default outgoing email."""

		info = JMAPConnectionInfo(self.server_url, self.username, self.get_password("app_password"))
		connection = JMAPConnection(info)

		if self.default_outgoing_email:
			identity_service = IdentityService(self.user, connection)

			if not identity_service.get_identity_id_by_email(self.default_outgoing_email):
				frappe.throw(
					_(
						"Default Outgoing Email {0} is not found in the identities of the JMAP account."
					).format(frappe.bold(self.default_outgoing_email))
				)

	def validate_tenant_bound_user(self) -> None:
		"""Validate that if the user is tenant-bound, then the JMAP username must be the same as the User name and a Mail Principal Binding must exist for the user."""

		if not is_tenant_bound_user(self.user):
			return

		if self.username != self.user:
			frappe.throw(_("JMAP Username must be the same as the User name."))

		tenant = get_tenant_for_user(self.user)

		if not frappe.db.exists(
			"Mail Principal Binding",
			{"tenant": tenant, "principal_name": self.username},
			"principal_name",
		):
			frappe.throw(
				_("Account {0} is not bound to Tenant {1}").format(
					frappe.bold(self.username), frappe.bold(tenant)
				)
			)

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

	if has_role(user, "Mail User"):
		return f"(`tabUser Settings`.user = '{user}')"

	return "1=0"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "User Settings":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True
	elif has_role(user, "Mail User"):
		return doc.user == user

	return False
