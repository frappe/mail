# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MailSyncHistory(Document):
	def before_insert(self) -> None:
		self.validate_duplicate()

	def validate_duplicate(self) -> None:
		"""Validate if the Mail Sync History already exists."""

		if frappe.db.exists(
			"Mail Sync History",
			{"source": self.source, "user": self.user},
		):
			frappe.throw(_("Mail Sync History already exists for this source and user."))


def create_mail_sync_history(
	source: str,
	user: str,
	last_received_at: str | None = None,
	commit: bool = False,
) -> "MailSyncHistory":
	"""Create a Mail Sync History."""

	doc = frappe.new_doc("Mail Sync History")
	doc.source = source
	doc.user = user
	doc.last_received_at = last_received_at
	doc.insert(ignore_permissions=True)

	if commit:
		frappe.db.commit()

	return doc


def get_mail_sync_history(source: str, user: str) -> "MailSyncHistory":
	"""Returns the Mail Sync History for the given source and user."""

	if name := frappe.db.exists("Mail Sync History", {"source": source, "user": user}):
		return frappe.get_doc("Mail Sync History", name)

	return create_mail_sync_history(source, user, commit=True)


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mail Sync History",
		["source", "user"],
		constraint_name="unique_source_user",
	)
