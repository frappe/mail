# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MailServerTLSCertificate(Document):
	pass


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mail Server TLS Certificate",
		["parenttype", "parent", "certificate_id"],
		constraint_name="unique_parent_certificate_id",
	)
