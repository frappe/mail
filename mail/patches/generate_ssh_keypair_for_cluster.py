import frappe
from frappe import _


def execute() -> None:
	clusters = frappe.db.get_all("Mail Cluster", {"ssh_public_key": ["in", ["", None]]}, pluck="name")
	for cluster in clusters:
		try:
			frappe.get_doc("Mail Cluster", cluster).generate_ssh_keypair(save=True)
		except Exception:
			frappe.log_error(
				title=_("Failed to generate SSH keypair"), message=frappe.get_traceback(with_context=False)
			)
