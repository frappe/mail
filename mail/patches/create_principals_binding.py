import frappe
from frappe.modules.utils import sync_customizations
from frappe.utils.password import get_decrypted_password

from mail.server.doctype.mail_principal_binding.mail_principal_binding import create_principal_binding
from mail.utils.cache import get_cluster_for_tenant

DOCTYPES = ["Mail Domain", "Mail Account", "Mailing List"]
TYPE_MAPPING = {
	"Mail Domain": "Domain",
	"Mail Account": "Individual",
	"Mailing List": "List",
}


def execute() -> None:
	sync_customizations(app="mail")
	for doctype in DOCTYPES:
		if not frappe.db.has_table(doctype):
			continue

		fields = ["name", "tenant"]
		if doctype == "Mail Domain":
			fields.append("is_verified")
		elif doctype == "Mail Account":
			fields.extend(["default_outgoing_email", "backup_email"])

		rows = frappe.db.get_all(doctype, filters={"enabled": 1}, fields=fields)

		for row in rows:
			if not frappe.db.exists("Mail Principal Binding", {"principal_name": row.name}):
				create_principal_binding(
					row.tenant, row.name, TYPE_MAPPING[doctype], bool(row.get("is_verified", 0))
				)

			if doctype == "Mail Account":
				app_password = get_decrypted_password(doctype, row.name, "app_password")
				jmap_server_url = frappe.db.get_value(
					"Mail Cluster", get_cluster_for_tenant(row.tenant), "base_url"
				)

				frappe.db.set_value(
					"User",
					row.name,
					{
						"jmap_server_url": jmap_server_url,
						"jmap_username": row.name,
						"jmap_app_password": app_password,
						"jmap_default_outgoing_email": row.default_outgoing_email,
						"backup_email": row.backup_email,
					},
				)
