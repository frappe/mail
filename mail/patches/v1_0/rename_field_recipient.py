import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	doctype = "Mail Recipient"
	old_fieldname = "recipient"
	new_fieldname = "email"

	if frappe.db.has_column(doctype, old_fieldname):
		rename_field(doctype, old_fieldname, new_fieldname)
