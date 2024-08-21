import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	doctype = "Outgoing Mail"
	old_fieldname = "newsletter"
	new_fieldname = "is_newsletter"

	if frappe.db.has_column(doctype, old_fieldname):
		rename_field(doctype, old_fieldname, new_fieldname)
