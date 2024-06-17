import frappe
from frappe import _
from frappe.utils import now, cint
from mail.utils.user import is_mailbox_owner
from mail.utils.validation import validate_mailbox_for_incoming
from mail.mail.doctype.mail_sync_history.mail_sync_history import get_mail_sync_history


@frappe.whitelist(methods=["GET"])
def pull(mailbox: str, limit: int = 50) -> list[str]:
	"""Returns the emails for the given mailbox."""

	source = frappe.request.headers.get("X-Site") or frappe.local.request_ip

	max_sync_via_api = cint(
		frappe.db.get_single_value("Mail Settings", "max_sync_via_api")
	)
	if limit > max_sync_via_api:
		frappe.throw(
			_("Cannot fetch more than {0} emails at a time").format(max_sync_via_api)
		)

	user = frappe.session.user
	if not is_mailbox_owner(mailbox, user):
		frappe.throw(_("Mailbox {0} is not associated with user {1}").format(mailbox, user))

	validate_mailbox_for_incoming(mailbox)

	sync_history = get_mail_sync_history(source, user, mailbox)

	IM = frappe.qb.DocType("Incoming Mail")
	query = (
		frappe.qb.from_(IM)
		.select(IM.delivered_at, IM.message)
		.where((IM.docstatus == 1) & (IM.receiver == mailbox))
		.orderby(IM.created_at)
		.limit(limit)
	)

	if sync_history.last_sync_at:
		query = query.where(IM.delivered_at > sync_history.last_sync_at)

	result = []
	last_sync_at = None
	for mail in query.run(as_dict=True):
		if not last_sync_at or mail.delivered_at > last_sync_at:
			last_sync_at = mail.delivered_at

		result.append(mail.message)

	frappe.db.set_value(
		sync_history.doctype, sync_history.name, "last_sync_at", last_sync_at or now()
	)
	frappe.db.commit()

	return result
