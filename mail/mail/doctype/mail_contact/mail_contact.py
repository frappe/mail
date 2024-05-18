# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import Optional
from mail.utils import is_system_manager
from frappe.model.document import Document


class MailContact(Document):
	def before_validate(self) -> None:
		self.set_user()

	def validate(self) -> None:
		self.validate_duplicate_contact()

	def set_user(self) -> None:
		"""Set user as current user if not set."""

		user = frappe.session.user
		if not self.user or not is_system_manager(user):
			self.user = user

	def validate_duplicate_contact(self) -> None:
		if frappe.db.exists("Mail Contact", {"email": self.email, "user": self.user}):
			frappe.throw(
				_("Mail Contact with email {0} already exists.").format(frappe.bold(self.email))
			)


def has_permission(doc: "Document", ptype: str, user: str) -> bool:
	if doc.doctype != "Mail Contact":
		return False

	return is_system_manager(user) or (user == doc.user)


def get_permission_query_condition(user: Optional[str]) -> str:
	if not user:
		user = frappe.session.user

	if is_system_manager(user):
		return ""

	return f"(`tabMail Contact`.`user` = {frappe.db.escape(user)})"
