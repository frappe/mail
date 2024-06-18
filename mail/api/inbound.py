import frappe
from frappe import _
from typing import Optional, TYPE_CHECKING
from mail.utils.user import is_mailbox_owner
from frappe.utils import now, cint, get_datetime
from mail.utils.validation import validate_mailbox_for_incoming
from mail.mail.doctype.mail_sync_history.mail_sync_history import get_mail_sync_history

if TYPE_CHECKING:
	from mail.mail.doctype.mail_sync_history.mail_sync_history import MailSyncHistory


@frappe.whitelist(methods=["GET"])
def pull(
	mailbox: str,
	limit: int = 50,
	after_datetime: Optional[str] = None,
) -> list[str]:
	"""Returns the emails for the given mailbox."""

	validate_mailbox(mailbox)
	validate_max_sync_limit(limit)
	validate_after_datetime(after_datetime)

	result = []
	last_sync_at = None
	source = frappe.request.headers.get("X-Site") or frappe.local.request_ip
	sync_history = get_mail_sync_history(source, frappe.session.user, mailbox)
	mails = get_incoming_mails(mailbox, limit, after_datetime or sync_history.last_sync_at)

	for mail in mails:
		if not last_sync_at or mail.processed_at > last_sync_at:
			last_sync_at = mail.processed_at

		result.append(mail.message)

	update_last_sync_at(sync_history, last_sync_at)

	return result


def validate_mailbox(mailbox: str) -> None:
	"""Validates if the mailbox is associated with the user and is valid for incoming emails."""

	user = frappe.session.user

	if not is_mailbox_owner(mailbox, user):
		frappe.throw(_("Mailbox {0} is not associated with user {1}").format(mailbox, user))

	validate_mailbox_for_incoming(mailbox)


def validate_max_sync_limit(limit: int) -> None:
	"""Validates if the limit is within the maximum limit set in the Mail Settings."""

	max_sync_limit = cint(
		frappe.db.get_single_value("Mail Settings", "max_sync_via_api", cache=True)
	)

	if limit > max_sync_limit:
		frappe.throw(_("Cannot fetch more than {0} emails at a time.").format(max_sync_limit))


def validate_after_datetime(after_datetime: str) -> None:
	"""Validates the datetime format for after_datetime."""

	if not get_datetime(after_datetime):
		frappe.throw(_("Invalid datetime format for after_datetime."))


def get_incoming_mails(
	mailbox: str,
	limit: int,
	after_datetime: Optional[str] = None,
) -> list[dict]:
	"""Returns the incoming mails for the given mailbox."""

	IM = frappe.qb.DocType("Incoming Mail")
	query = (
		frappe.qb.from_(IM)
		.select(IM.processed_at, IM.message)
		.where((IM.docstatus == 1) & (IM.receiver == mailbox))
		.orderby(IM.created_at)
		.limit(limit)
	)

	if after_datetime:
		query = query.where(IM.processed_at > after_datetime)

	return query.run(as_dict=True)


def update_last_sync_at(sync_history: "MailSyncHistory", last_sync_at: str) -> None:
	"""Update the last_sync_at in the Mail Sync History."""

	frappe.db.set_value(
		sync_history.doctype, sync_history.name, "last_sync_at", last_sync_at or now()
	)
	frappe.db.commit()
