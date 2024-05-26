import frappe
from frappe.query_builder import Case


@frappe.whitelist(methods=["GET"], allow_guest=True)
def open(id: str) -> None:
	"""Updates Outgoing Mail opened status."""

	try:
		now = frappe.utils.now()
		OM = frappe.qb.DocType("Outgoing Mail")
		(
			frappe.qb.update(OM)
			.set(OM.opened, 1)
			.set(
				OM.first_opened_at,
				Case().when(OM.first_opened_at.isnull(), now).else_(OM.first_opened_at),
			)
			.set(OM.last_opened_at, now)
			.set(OM.opened_count, OM.opened_count + 1)
			.where((OM.docstatus == 1) & (OM.tracking_id == id))
		).run()
	except Exception:
		frappe.log_error(
			title="Error Updating Outgoing Mail Opened Status", message=frappe.get_traceback()
		)
	finally:
		frappe.db.commit()
		frappe.response.update(frappe.utils.get_imaginary_pixel_response())
