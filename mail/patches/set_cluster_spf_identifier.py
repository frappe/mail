import frappe
from frappe import _


def execute() -> None:
	clusters = frappe.db.get_all("Mail Cluster", {"spf_identifier": ["in", ["", None]]}, pluck="name")
	try:
		for cluster in clusters:
			doc = frappe.get_doc("Mail Cluster", cluster)
			doc.validate_spf_identifier()
			doc.save()
	except Exception:
		frappe.log_error(
			title=_("Error setting SPF Identifier for Mail Cluster"), message=frappe.get_traceback()
		)
