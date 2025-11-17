# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MailClusterStore(Document):
	pass


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mail Cluster Store",
		["parenttype", "parent", "store_id"],
		constraint_name="unique_parent_store_id",
	)
