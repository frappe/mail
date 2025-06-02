# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from mail.backend import MailBackendMailingListManager
from mail.utils import normalize_email
from mail.utils.cache import get_cluster_for_tenant, get_tenant_for_domain, get_tenant_for_user
from mail.utils.user import has_role, is_system_manager, is_tenant_admin
from mail.utils.validation import (
	is_email_assigned,
	is_subaddressed_email,
	is_valid_email_for_domain,
	validate_domain_is_enabled_and_verified,
	validate_domain_owned_by_tenant,
)


class MailingList(Document):
	def autoname(self) -> None:
		self.email = self.email.strip().lower()
		self.name = self.email

	def before_validate(self) -> None:
		self.set_tenant()

	def validate(self) -> None:
		self.validate_enabled()
		self.validate_domain()
		self.validate_email()
		self.set_normalized_email()
		self.validate_tenant_max_max_mailing_lists()

	def on_update(self) -> None:
		self.clear_cache()

		if self.enabled:
			if self.has_value_changed("enabled") or self.has_value_changed("email"):
				members = frappe.db.get_all(
					"Mailing List Member", filters={"mailing_list": self.name}, pluck="member_name"
				)
				external_members = frappe.db.get_all(
					"Mailing List External Member", filters={"mailing_list": self.name}, pluck="member_email"
				)
				MailBackendMailingListManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).create(
					self.email, self.display_name, members=members, external_members=external_members
				)
			elif self.has_value_changed("display_name"):
				MailBackendMailingListManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).update(
					self.email, self.display_name
				)
		elif self.has_value_changed("enabled"):
			MailBackendMailingListManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).delete(
				self.email
			)

	def on_trash(self) -> None:
		self.clear_cache()

		if self.enabled:
			MailBackendMailingListManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).delete(
				self.email
			)

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
			frappe.throw(_("Mail Alias {0} is enabled. Please disable it first.").format(frappe.bold(alias)))

	def validate_domain(self) -> None:
		"""Validates the domain."""

		validate_domain_owned_by_tenant(self.domain_name, self.tenant)
		validate_domain_is_enabled_and_verified(self.domain_name)

	def validate_email(self) -> None:
		"""Validates the email address."""

		is_subaddressed_email(self.email, raise_exception=True)
		is_email_assigned(self.email, self.doctype, raise_exception=True)
		is_valid_email_for_domain(self.email, self.domain_name, raise_exception=True)

	def set_normalized_email(self) -> None:
		"""Sets the normalized email."""

		if not self.normalized_email:
			self.normalized_email = normalize_email(self.email)

	def validate_tenant_max_max_mailing_lists(self) -> None:
		"""Validates the Tenant Max Mailing Lists."""

		total_mailing_lists = frappe.db.count("Mailing List", filters={"tenant": self.tenant, "enabled": 1})
		max_mailing_lists = frappe.db.get_value("Mail Tenant", self.tenant, "max_mailing_lists")
		if total_mailing_lists >= max_mailing_lists:
			frappe.throw(
				_("You have reached the maximum limit of {0} mailing lists for the tenant.").format(
					frappe.bold(max_mailing_lists)
				)
			)

	def clear_cache(self) -> None:
		"""Clears the Cache."""

		frappe.cache.hdel(f"mailing_list|{self.name}", "tenant")
		frappe.cache.hdel(f"tenant|{self.tenant}", "mailing_lists")


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mailing List":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True

	if is_tenant_admin(doc.tenant, user):
		return True

	return False


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	if has_role(user, "Mail Admin"):
		if tenant := get_tenant_for_user(user):
			return f"(`tabMailing List`.`tenant` = {frappe.db.escape(tenant)})"

	return "1=0"
