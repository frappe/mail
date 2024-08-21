import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	old_fieldname = "verified"
	new_fieldname = "is_verified"

	for doctype in ["Mail Domain", "DNS Record"]:
		if frappe.db.has_column(doctype, old_fieldname):
			rename_field(doctype, old_fieldname, new_fieldname)
