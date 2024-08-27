import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	fields_to_rename = [
		("reply_to_mail_type", "in_reply_to_mail_type"),
		("reply_to_mail_name", "in_reply_to_mail_name"),
	]

	for doctype in ["Incoming Mail", "Outgoing Mail"]:
		for old_fieldname, new_fieldname in fields_to_rename:
			if frappe.db.has_column(doctype, old_fieldname):
				rename_field(doctype, old_fieldname, new_fieldname)
