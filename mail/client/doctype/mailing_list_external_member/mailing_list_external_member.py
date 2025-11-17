# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from mail.backend import MailBackendMailingListManager
from mail.utils.cache import (
	get_cluster_for_tenant,
	get_mailing_lists_owned_by_tenant,
	get_tenant_for_mailing_list,
	get_tenant_for_user,
)
from mail.utils.user import has_role, is_system_manager


class MailingListExternalMember(Document):
	def validate(self) -> None:
		self.validate_mailing_list()
		self.validate_member_email()

	def validate_mailing_list(self) -> None:
		"""Validate if the Mailing List is enabled."""

		if not frappe.db.get_value("Mailing List", self.mailing_list, "enabled"):
			frappe.throw(_("The Mailing List {0} is disabled.").format(frappe.bold(self.mailing_list)))

	def validate_member_email(self) -> None:
		"""Validate if the member email is not the same as the Mailing List."""

		self.member_email = self.member_email.strip().lower()

		if self.mailing_list == self.member_email:
			frappe.throw(_("Member cannot be the same as the Mailing List."))

		for doctype in ["Mail Account", "Mail Alias", "Mailing List"]:
			if frappe.db.exists(doctype, self.member_email):
				frappe.throw(
					_(
						"The email address {0} is already used as a {1} in this system and cannot be added as an external member."
					).format(frappe.bold(self.member_email), doctype)
				)

	def after_insert(self) -> None:
		MailBackendMailingListManager(
			"Mail Cluster", get_cluster_for_tenant(get_tenant_for_mailing_list(self.mailing_list))
		).add_member(self.mailing_list, self.member_email, is_external=True)

	def on_trash(self) -> None:
		if frappe.db.get_value("Mailing List", self.mailing_list, "enabled"):
			MailBackendMailingListManager(
				"Mail Cluster", get_cluster_for_tenant(get_tenant_for_mailing_list(self.mailing_list))
			).remove_member(self.mailing_list, self.member_email, is_external=True)


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mailing List External Member":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True

	if has_role(user, "Mail Admin"):
		if tenant := get_tenant_for_user(user):
			return doc.mailing_list in get_mailing_lists_owned_by_tenant(tenant)

	return False


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	if has_role(user, "Mail Admin"):
		if tenant := get_tenant_for_user(user):
			if mailing_lists := get_mailing_lists_owned_by_tenant(tenant):
				return f'(`tabMailing List External Member`.`mailing_list` IN ({", ".join([frappe.db.escape(mailing_list) for mailing_list in mailing_lists])}))'

	return "1=0"


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mailing List External Member",
		["mailing_list", "member_email"],
		constraint_name="unique_mailing_list_member",
	)
