# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from mail.utils.user import is_system_manager


class MailContact(Document):
	def before_validate(self) -> None:
		self.set_user()

	def set_user(self) -> None:
		"""Set user as current user if not set."""

		if not self.user:
			self.user = frappe.session.user


def create_mail_contact(user: str, email: str, display_name: str | None = None) -> None:
	"""Creates the mail contact."""

	if not frappe.db.exists("Mail Contact", {"user": user, "email": email}):
		doc = frappe.new_doc("Mail Contact")
		doc.user = user
		doc.email = email
		doc.display_name = display_name
		doc.insert(ignore_permissions=True, ignore_if_duplicate=True)


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Contact":
		return False

	user = user or frappe.session.user

	return (user == doc.user) or is_system_manager(user)


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	return f"(`tabMail Contact`.`user` = {frappe.db.escape(user)})"


def on_doctype_update() -> None:
	frappe.db.add_unique("Mail Contact", ["user", "email"], constraint_name="unique_user_email")
