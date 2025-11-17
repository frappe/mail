# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MailServerListener(Document):
	pass


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mail Server Listener",
		["parenttype", "parent", "listener_id"],
		constraint_name="unique_parent_listener_id",
	)
