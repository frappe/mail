# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from typing import Optional
from frappe.model.document import Document


class MailSyncHistory(Document):
	def before_insert(self) -> None:
		self.validate_duplicate()

	def validate_duplicate(self) -> None:
		"""Validate if the Mail Sync History already exists."""

		if frappe.db.exists(
			"Mail Sync History", {"site": self.site, "user": self.user, "mailbox": self.mailbox}
		):
			frappe.throw("Mail Sync History already exists for this site, user and mailbox")


def create_mail_sync_history(
	site: str,
	user: str,
	mailbox: str,
	last_sync_at: Optional[str] = None,
	commit: bool = False,
) -> "MailSyncHistory":
	"""Create a Mail Sync History."""

	doc = frappe.new_doc("Mail Sync History")
	doc.site = site
	doc.user = user
	doc.mailbox = mailbox
	doc.last_sync_at = last_sync_at
	doc.insert(ignore_permissions=True)

	if commit:
		frappe.db.commit()

	return doc


def get_mail_sync_history(site: str, user: str, mailbox: str) -> "MailSyncHistory":
	"""Returns the Mail Sync History for the given site, user and mailbox."""

	if name := frappe.db.exists(
		"Mail Sync History", {"site": site, "user": user, "mailbox": mailbox}
	):
		return frappe.get_doc("Mail Sync History", name)

	return create_mail_sync_history(site, user, mailbox, commit=True)
