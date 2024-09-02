import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	doctype = "Mail Domain"
	old_fieldname, new_fieldname = "dkim_bits", "dkim_key_size"

	if frappe.db.has_column(doctype, old_fieldname):
		rename_field(doctype, old_fieldname, new_fieldname)
