# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe.model.document import Document

from mail.utils.user import has_role, is_system_manager, is_tenant_admin


class MailboxSettings(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_duplicate()

	def validate_duplicate(self) -> None:
		"""Checks for duplicate Mailbox Settings for the same user and mailbox ID."""

		existing = frappe.db.exists(
			"Mailbox Settings",
			{
				"user": self.user,
				"mailbox_id": self.mailbox_id,
				"name": ["!=", self.name],
			},
		)

		if existing:
			frappe.throw(
				f"Mailbox Settings for user {frappe.bold(self.user)} with mailbox ID {frappe.bold(self.mailbox_id)} already exists.",
				title="Duplicate Mailbox Settings",
			)


def on_doctype_update() -> None:
	frappe.db.add_unique("Mailbox Settings", ["user", "mailbox_id"], constraint_name="unique_user_mailbox")


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	if has_role(user, "Mail User"):
		return f"(`tabMailbox Settings`.user = '{user}')"

	return "1=0"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mailbox Settings":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True
	elif has_role(user, "Mail User"):
		return doc.user == user

	return False
