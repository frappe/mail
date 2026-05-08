# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from mail.jmap import parse_account


class MailSyncHistory(Document):
	def before_insert(self) -> None:
		self.validate_duplicate()
		self.user = parse_account(self.account)[0]

	def validate_duplicate(self) -> None:
		"""Validate if the Mail Sync History already exists."""

		if frappe.db.exists(
			"Mail Sync History",
			{"account": self.account, "source": self.source},
		):
			frappe.throw(_("Mail Sync History already exists for this account and source."))


def create_mail_sync_history(
	account: str,
	source: str,
	last_received_at: str | None = None,
	commit: bool = False,
) -> "MailSyncHistory":
	"""Create a Mail Sync History."""

	doc = frappe.new_doc("Mail Sync History")
	doc.account = account
	doc.source = source
	doc.last_received_at = last_received_at
	doc.insert(ignore_permissions=True)

	if commit:
		frappe.db.commit()

	return doc


def get_mail_sync_history(account: str, source: str) -> "MailSyncHistory":
	"""Returns the Mail Sync History for the given account and source."""

	if name := frappe.db.exists("Mail Sync History", {"account": account, "source": source}):
		return frappe.get_doc("Mail Sync History", name)

	return create_mail_sync_history(account, source, commit=True)


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mail Sync History",
		["account", "source"],
		constraint_name="unique_account_source",
	)
