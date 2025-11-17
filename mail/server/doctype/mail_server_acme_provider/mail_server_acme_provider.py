# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MailServerACMEProvider(Document):
	pass


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mail Server ACME Provider",
		["parenttype", "parent", "directory_id"],
		constraint_name="unique_parent_directory_id",
	)
