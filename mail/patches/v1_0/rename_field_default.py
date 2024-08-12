import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	doctype = "Mailbox"
	old_fieldname = "default"
	new_fieldname = "is_default"

	if frappe.db.has_column(doctype, old_fieldname):
		rename_field(doctype, old_fieldname, new_fieldname)
