import frappe
from frappe import _


def validate_file(doc, method):
	def throw(msg, raise_exception=True, indicator="red", alert=True):
		frappe.msgprint(
			msg, raise_exception=raise_exception, indicator=indicator, alert=alert
		)

	if (
		doc.attached_to_doctype in ["Outgoing Mail", "Incoming Mail"] and doc.attached_to_name
	):
		docstatus = frappe.db.get_value(
			doc.attached_to_doctype, doc.attached_to_name, "docstatus"
		)

		if method == "validate":
			if doc.is_new() and docstatus > 0:
				throw(
					_("Cannot attach file to a submitted/cancelled {0} {1}.").format(
						doc.attached_to_doctype, frappe.bold(doc.attached_to_name)
					)
				)

			if doc.attached_to_doctype == "Outgoing Mail":
				file_size = doc.file_size / 1024 / 1024
				max_attachment_size = frappe.db.get_single_value(
					"Mail Settings", "outgoing_max_attachment_size"
				)

				if file_size > max_attachment_size:
					throw(
						_("Attachment size limit exceeded. Maximum {0} MB allowed.").format(
							frappe.bold(max_attachment_size)
						)
					)

		elif method == "on_update":
			if docstatus > 0:
				throw(
					_("Cannot update attachment as it is linked with {0} {1}.").format(
						doc.attached_to_doctype, frappe.bold(doc.attached_to_name)
					)
				)

		elif method == "on_trash":
			if docstatus > 0:
				throw(
					_("Cannot delete attachment as it is linked with {0} {1}.").format(
						doc.attached_to_doctype, frappe.bold(doc.attached_to_name)
					)
				)
