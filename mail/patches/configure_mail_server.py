import frappe
from frappe import _

from mail.utils import execute_with_logging


def execute() -> None:
	def _configure(server) -> None:
		doc = frappe.get_doc("Mail Server", server)
		doc.recovery_http_port = doc.recovery_http_port or 8080
		doc.bootstrap_ndjson = doc.bootstrap_ndjson or doc._generate_bootstrap_ndjson()
		doc.save()

	for server in frappe.db.get_all("Mail Server", {}, pluck="name"):
		execute_with_logging(
			func=lambda: _configure(server),
			title=_("Failed to configure Mail Server {0}").format(frappe.bold(server)),
		)
