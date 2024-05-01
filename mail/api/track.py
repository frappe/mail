import frappe
from frappe.query_builder import Case
from frappe.utils.response import redirect


@frappe.whitelist(methods=["GET"], allow_guest=True)
def open(id: str) -> None:
	"""Updates Outgoing Mail opened status."""

	if id:
		now = frappe.utils.now()
		OM = frappe.qb.DocType("Outgoing Mail")
		first_opened_at_condition = (
			Case().when(OM.first_opened_at.isnull(), now).else_(OM.first_opened_at)
		)
		(
			frappe.qb.update(OM)
			.set(OM.opened, 1)
			.set(OM.first_opened_at, first_opened_at_condition)
			.set(OM.last_opened_at, now)
			.set(OM.opened_count, OM.opened_count + 1)
			.where((OM.docstatus == 1) & (OM.tracking_id == id))
		).run()
		frappe.db.commit()

	frappe.response.location = "/assets/mail/images/pixel.png"
	return redirect()
