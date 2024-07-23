import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	doctype = "Outgoing Mail"
	field_map = {
		"subdomain": "is_subdomain",
		"root_domain": "is_root_domain",
	}

	for old_fieldname, new_fieldname in field_map.items():
		if frappe.db.has_column(doctype, old_fieldname):
			rename_field(doctype, old_fieldname, new_fieldname)
