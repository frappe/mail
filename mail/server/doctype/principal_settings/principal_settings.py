# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import Literal
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.utils.user import has_role, is_mail_admin, is_system_manager


class PrincipalSettings(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_is_verified()

	def validate_is_verified(self) -> None:
		"""Sets is_verified to 0 for non-domain principals."""

		if self.principal_type != "Domain":
			self.is_verified = 0


def create_principal_settings(
	principal_name: str,
	principal_type: Literal["API Key", "Domain", "Group", "Individual", "List", "OAuth Client", "Role"],
	is_verified: bool = False,
) -> "PrincipalSettings":
	"""Create a Principal Settings document."""

	settings = frappe.new_doc("Principal Settings")
	settings.principal_name = principal_name
	settings.principal_type = principal_type
	settings.is_verified = cint(is_verified)
	settings.flags.ignore_links = True
	settings.insert(ignore_permissions=True)

	return settings


def get_local_principals(
	principal_type: str | None = None, text: str | None = None, page: int = 1, limit: int = 10
) -> tuple[list[str], int]:
	"""Returns a list of local principal names based on the given filters and pagination parameters."""

	filters = {}
	if principal_type:
		filters["principal_type"] = principal_type
	if text:
		filters["principal_name"] = ["like", f"%{text}%"]

	if total := frappe.db.count("Principal Settings", filters):
		return frappe.db.get_all(
			"Principal Settings",
			filters=filters,
			pluck="principal_name",
			start=(page - 1) * limit,
			limit=limit,
		), total

	return [], 0


def update_principal_settings(pname: str, **kwargs) -> None:
	"""Update a Principal Settings document."""

	if settings := frappe.db.exists("Principal Settings", {"principal_name": pname}):
		doc = frappe.get_doc("Principal Settings", settings)
		for key, value in kwargs.items():
			setattr(doc, key, value)
		doc.flags.ignore_links = True
		doc.save(ignore_permissions=True)


def delete_principal_settings(principal_name: str) -> None:
	"""Delete a Principal Settings document."""

	if settings := frappe.db.exists("Principal Settings", {"principal_name": principal_name}):
		frappe.delete_doc("Principal Settings", settings, ignore_permissions=True)


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user) or is_mail_admin(user):
		return ""

	return "1=0"


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Principal Settings":
		return False

	user = user or frappe.session.user
	if is_system_manager(user):
		return True
	elif is_mail_admin(user):
		if ptype == "read":
			return True

	return False
