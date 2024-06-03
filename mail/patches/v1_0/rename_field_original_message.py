import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	old_fieldname = "original_message"
	new_fieldname = "message"

	for doctype in ["Outgoing Mail", "Incoming Mail"]:
		if frappe.db.has_column(doctype, old_fieldname):
			rename_field(doctype, old_fieldname, new_fieldname)
