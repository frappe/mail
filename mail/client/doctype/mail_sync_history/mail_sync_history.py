# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from mail.jmap import parse_account
from mail.utils.user import get_account_scoped_permission_query, has_account_scoped_permission


class MailSyncHistory(Document):
	"""Per-source inbound-pull watermark, shared per JMAP account ID — every user with
	access to the account shares the same last-received state for a given source."""

	def before_insert(self) -> None:
		self.validate_duplicate()

	def validate_duplicate(self) -> None:
		"""Validate if the Mail Sync History already exists."""

		if frappe.db.exists(
			"Mail Sync History",
			{"account_id": self.account_id, "source": self.source},
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
	doc.account_id = parse_account(account)[1]
	doc.source = source
	doc.last_received_at = last_received_at
	doc.insert(ignore_permissions=True)

	if commit:
		frappe.db.commit()

	return doc


def get_mail_sync_history(account: str, source: str) -> "MailSyncHistory":
	"""Returns the Mail Sync History for the given account and source."""

	account_id = parse_account(account)[1]
	if name := frappe.db.exists("Mail Sync History", {"account_id": account_id, "source": source}):
		return frappe.get_doc("Mail Sync History", name)

	return create_mail_sync_history(account, source, commit=True)


def get_permission_query_condition(user: str | None = None) -> str:
	return get_account_scoped_permission_query("Mail Sync History", user=user)


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Sync History":
		return False

	return has_account_scoped_permission(doc, user=user)


def on_doctype_update() -> None:
	# Sync history is shared per account_id, so uniqueness is on (account_id, source).
	frappe.db.add_unique(
		"Mail Sync History",
		["account_id", "source"],
		constraint_name="unique_account_id_source",
	)
