import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	doctype = "Incoming Mail"
	fields_to_rename = [
		("delivered_at", "processed_at"),
		("delivered_after", "processed_after"),
	]

	for old_fieldname, new_fieldname in fields_to_rename:
		if frappe.db.has_column(doctype, old_fieldname):
			rename_field(doctype, old_fieldname, new_fieldname)
