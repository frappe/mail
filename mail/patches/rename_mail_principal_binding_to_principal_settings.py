import frappe

OLD_DOCTYPE = "Mail Principal Binding"
NEW_DOCTYPE = "Principal Settings"


def execute() -> None:
	if frappe.db.table_exists(OLD_DOCTYPE) and not frappe.db.table_exists(NEW_DOCTYPE):
		frappe.rename_doc("DocType", OLD_DOCTYPE, NEW_DOCTYPE, force=True)
		frappe.reload_doc("server", "doctype", frappe.scrub(NEW_DOCTYPE))
		frappe.delete_doc("DocType", OLD_DOCTYPE, force=1)
