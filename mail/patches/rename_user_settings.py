from uuid import uuid7

import frappe


def execute() -> None:
	for settings in frappe.db.get_all("User Settings", pluck="name"):
		doc = frappe.get_doc("User Settings", settings)
		doc.rename(str(uuid7()), force=True)
