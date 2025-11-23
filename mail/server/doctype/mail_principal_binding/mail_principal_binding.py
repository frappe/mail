# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import Literal

import frappe
from frappe import _
from frappe.model.document import Document
from uuid_utils import uuid7


class MailPrincipalBinding(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_principal()

	def validate_principal(self) -> None:
		self.principal = f"{self.tenant}|{self.principal_name}"


def create_principal_binding(
	tenant: str,
	principal_name: str,
	principal_type: Literal["API Key", "Domain", "Group", "Individual", "List", "OAuth Client", "Role"],
) -> "MailPrincipalBinding":
	"""Create a Mail Principal Binding document."""

	binding = frappe.new_doc("Mail Principal Binding")
	binding.tenant = tenant
	binding.principal_name = principal_name
	binding.principal_type = principal_type
	binding.flags.ignore_links = True
	binding.insert(ignore_permissions=True)

	return binding


def get_tenant_principals(
	tenant: str, principal_type: str | None = None, text: str | None = None, page: int = 1, limit: int = 10
) -> tuple[list[str], int]:
	"""Returns a list of principal names for the given tenant."""

	filters = {"tenant": tenant}
	if principal_type:
		filters["principal_type"] = principal_type
	if text:
		filters["principal_name"] = ["like", f"%{text}%"]

	if total := frappe.db.count("Mail Principal Binding", filters):
		return frappe.db.get_all(
			"Mail Principal Binding",
			filters=filters,
			pluck="principal_name",
			start=(page - 1) * limit,
			limit=limit,
		), total

	return [], 0


def _get_tenant_principals(tenant: str, principal_type: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of principals of the given type for the given tenant."""

	return frappe.db.get_all(
		"Mail Principal Binding",
		filters={"tenant": tenant, "principal_type": principal_type},
		order_by=order_by,
		pluck="principal_name",
	)


def get_tenant_api_keys(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of API Key principals for the given tenant."""

	return _get_tenant_principals(tenant, "API Key", order_by)


def get_tenant_domains(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of domain principals for the given tenant."""

	return _get_tenant_principals(tenant, "Domain", order_by)


def get_tenant_groups(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of group principals for the given tenant."""

	return _get_tenant_principals(tenant, "Group", order_by)


def get_tenant_individuals(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of individual principals for the given tenant."""

	return _get_tenant_principals(tenant, "Individual", order_by)


def get_tenant_lists(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of list principals for the given tenant."""

	return _get_tenant_principals(tenant, "List", order_by)


def get_tenant_oauth_clients(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of OAuth Client principals for the given tenant."""

	return _get_tenant_principals(tenant, "OAuth Client", order_by)


def get_tenant_roles(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of Role principals for the given tenant."""

	return _get_tenant_principals(tenant, "Role", order_by)


def get_tenant_emails(tenant: str, order_by: str = "creation desc") -> list[str]:
	"""Returns a list of email addresses associated with the given tenant."""

	return frappe.db.get_all(
		"Mail Principal Binding",
		filters={"tenant": tenant, "principal_type": ["in", ["Group", "Individual", "List"]]},
		order_by=order_by,
		pluck="principal_name",
	)


def delete_principal_binding(tenant: str, principal_name: str, raise_exception: bool = True) -> None:
	"""Delete a Mail Principal Binding document."""

	if binding := frappe.db.exists(
		"Mail Principal Binding", {"tenant": tenant, "principal_name": principal_name}
	):
		frappe.delete_doc("Mail Principal Binding", binding, ignore_permissions=True)
	elif raise_exception:
		frappe.throw(
			_("No Mail Principal Binding found for tenant: {0} and principal name: {1}").format(
				frappe.bold(tenant), frappe.bold(principal_name)
			)
		)


def ensure_principal_belong_to_tenant(tenant: str, principal_name: str) -> None:
	"""Ensure that the principal belongs to the given tenant."""

	if not frappe.db.exists("Mail Principal Binding", {"tenant": tenant, "principal_name": principal_name}):
		frappe.throw(
			_("Principal {0} does not belong to tenant {1}.").format(
				frappe.bold(principal_name), frappe.bold(tenant)
			)
		)


def ensure_emails_belong_to_tenant_domains(tenant: str, emails: list[str]) -> None:
	"""Ensure that the email domains belong to the given tenant."""

	domains = get_tenant_domains(tenant)
	tenant_name = frappe.db.get_value("Mail Tenant", tenant, "tenant_name")

	for email in emails:
		_user, domain = email.split("@", 1)
		if domain not in domains:
			frappe.throw(
				_("Email domain {0} is not associated with tenant {1}.").format(
					frappe.bold(domain), frappe.bold(tenant_name)
				)
			)


def ensure_groups_belong_to_tenant(tenant: str, groups: list[str]) -> None:
	"""Ensure that the groups belong to the given tenant."""

	tenant_groups = get_tenant_groups(tenant)
	tenant_name = frappe.db.get_value("Mail Tenant", tenant, "tenant_name")

	for group in groups:
		if group not in tenant_groups:
			frappe.throw(
				_("Group {0} is not associated with tenant {1}.").format(
					frappe.bold(group), frappe.bold(tenant_name)
				)
			)


def ensure_lists_belong_to_tenant(tenant: str, lists: list[str]) -> None:
	"""Ensure that the lists belong to the given tenant."""

	tenant_lists = get_tenant_lists(tenant)
	tenant_name = frappe.db.get_value("Mail Tenant", tenant, "tenant_name")

	for lst in lists:
		if lst not in tenant_lists:
			frappe.throw(
				_("List {0} is not associated with tenant {1}.").format(
					frappe.bold(lst), frappe.bold(tenant_name)
				)
			)


def ensure_members_belong_to_tenant(tenant: str, members: list[str]) -> None:
	"""Ensure that the members belong to the given tenant."""

	tenant_emails = frappe.db.get_all(
		"Mail Principal Binding",
		filters={"tenant": tenant, "principal_type": ["in", ["Group", "Individual"]]},
		pluck="principal_name",
	)
	tenant_name = frappe.db.get_value("Mail Tenant", tenant, "tenant_name")

	for member in members:
		if member not in tenant_emails:
			frappe.throw(
				_("Member {0} is not associated with tenant {1}.").format(
					frappe.bold(member), frappe.bold(tenant_name)
				)
			)


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mail Principal Binding",
		["tenant", "principal_name"],
		constraint_name="unique_tenant_principal_name",
	)
