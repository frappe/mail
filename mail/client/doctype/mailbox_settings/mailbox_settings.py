# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe.model.document import Document


class MailboxSettings(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())


def on_doctype_update() -> None:
	frappe.db.add_unique("Mailbox Settings", ["user", "mailbox_id"], constraint_name="unique_user_mailbox")
