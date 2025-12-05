import frappe

from mail.server.doctype.mail_principal_binding.mail_principal_binding import create_principal_binding
from mail.utils.cache import get_cluster_for_tenant

DOCTYPES = ["Mail Domain", "Mail Account", "Mailing List"]
TYPE_MAPPING = {
	"Mail Domain": "Domain",
	"Mail Account": "Individual",
	"Mailing List": "List",
}


def execute() -> None:
	for doctype in DOCTYPES:
		if frappe.db.has_table(doctype):
			fields = ["name", "tenant"]
			if doctype == "Mail Account":
				fields.append("is_verified")

			for row in frappe.db.get_all(doctype, {"enabled": 1}, fields=fields):
				if not frappe.db.exists("Mail Principal Binding", {"principal_name": row.name}):
					create_principal_binding(
						row.tenant, row.name, TYPE_MAPPING[doctype], bool(row.get("is_verified", 0))
					)

				if doctype == "Mail Account":
					account = frappe.get_doc("Mail Account", row.name)
					jmap_server_url = frappe.db.get_value(
						"Mail Cluster", get_cluster_for_tenant(row.tenant), "base_url"
					)

					user = frappe.get_doc("User", row.name)
					user.jmap_server_url = jmap_server_url
					user.jmap_username = row.name
					user.jmap_app_password = account.get_password("app_password")
					user.save(ignore_permissions=True)
