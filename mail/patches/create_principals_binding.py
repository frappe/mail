import frappe
from frappe.modules.utils import sync_customizations
from frappe.utils.password import get_decrypted_password

from mail.server.doctype.principal_settings.principal_settings import create_principal_settings
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
			if not frappe.db.exists("Principal Settings", {"principal_name": row.name}):
				create_principal_settings(
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
