import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	doctype = "Incoming Mail"
	field_map = {
		"spf": "spf_pass",
		"dkim": "dkim_pass",
		"dmarc": "dmarc_pass",
	}

	for old_fieldname, new_fieldname in field_map.items():
		if frappe.db.has_column(doctype, old_fieldname):
			rename_field(doctype, old_fieldname, new_fieldname)
