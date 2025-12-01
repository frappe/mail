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
		self.validate_is_verified()

	def validate_is_verified(self) -> None:
		"""Sets is_verified to 0 for non-domain principals."""

		if self.principal_type != "Domain":
			self.is_verified = 0


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


def update_principal_binding(pname: str, **kwargs) -> None:
	"""Update a Mail Principal Binding document."""

	if binding := frappe.db.exists("Mail Principal Binding", {"principal_name": pname}):
		doc = frappe.get_doc("Mail Principal Binding", binding)
		for key, value in kwargs.items():
			setattr(doc, key, value)
		doc.flags.ignore_links = True
		doc.save(ignore_permissions=True)


def delete_principal_binding(principal_name: str, raise_exception: bool = True) -> None:
	"""Delete a Mail Principal Binding document."""

	if binding := frappe.db.exists("Mail Principal Binding", {"principal_name": principal_name}):
		frappe.delete_doc("Mail Principal Binding", binding, ignore_permissions=True)
	elif raise_exception:
		frappe.throw(
			_("No Mail Principal Binding found for principal name: {0}").format(frappe.bold(principal_name))
		)
