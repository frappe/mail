import frappe
from frappe import _

from mail.utils import log_error


def execute() -> None:
	clusters = frappe.db.get_all("Mail Cluster", {"ssh_public_key": ["in", ["", None]]}, pluck="name")
	for cluster in clusters:
		try:
			frappe.get_doc("Mail Cluster", cluster).generate_ssh_keypair(save=True)
		except Exception:
			log_error(
				_("Failed to generate SSH keypair"), frappe.get_traceback(with_context=False)
			)
