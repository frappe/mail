import frappe

from mail.server.doctype.mail_principal_binding.mail_principal_binding import create_principal_binding

DOCTYPES = ["Mail Domain", "Mail Account", "Mailing List"]
TYPE_MAPPING = {
	"Mail Domain": "Domain",
	"Mail Account": "Individual",
	"Mailing List": "List",
}


def execute() -> None:
	for doctype in DOCTYPES:
		if frappe.db.has_table(doctype):
			for row in frappe.db.get_all(doctype, {"enabled": 1}, ["name", "tenant"]):
				if not frappe.db.exists("Mail Principal Binding", {"principal_name": row.name}):
					create_principal_binding(row.tenant, row.name, TYPE_MAPPING[doctype])
