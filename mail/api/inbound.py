import base64
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.utils import cint, convert_utc_to_system_timezone, create_batch, now

from mail.api.auth import validate_user
from mail.jmap import get_mailbox_id_by_role
from mail.mail.doctype.mail_message.mail_message import fetch_blobs, fetch_messages
from mail.mail.doctype.mail_sync_history.mail_sync_history import get_mail_sync_history
from mail.utils.cache import get_account_for_user
from mail.utils.dt import convert_to_utc
from mail.utils.rate_limiter import dynamic_rate_limit

if TYPE_CHECKING:
	from mail.mail.doctype.mail_sync_history.mail_sync_history import MailSyncHistory


@frappe.whitelist(methods=["GET"])
@dynamic_rate_limit()
def fetch_blob(blob_id: str, as_bytes: bool = False) -> str | bytes:
	"""Fetches the blob for the given blob_id."""

	validate_user()

	from mail.mail.doctype.mail_message.mail_message import fetch_blob as _fetch_blob

	blob = _fetch_blob(get_account(), blob_id)
	return blob if as_bytes else base64.b64encode(blob).decode("utf-8")


@frappe.whitelist(methods=["GET"])
@dynamic_rate_limit()
def pull(
	mailbox: str | None = None, limit: int = 50, last_received_at: str | None = None
) -> dict[str, list[dict] | str]:
	"""Returns the emails for the given mailbox."""

	validate_user()
	validate_max_sync_limit(limit)

	result = []
	source = get_source()
	mailbox = mailbox or "inbox"
	last_received_at = convert_to_system_timezone(last_received_at)
	sync_history = get_mail_sync_history(source, frappe.session.user, get_account())
	result = get_mails(mailbox, limit, last_received_at or sync_history.last_received_at)
	update_mail_sync_history(sync_history, result["last_received_at"], result["last_received_mail"])
	result["last_received_at"] = convert_to_utc(result["last_received_at"])

	return result


@frappe.whitelist(methods=["GET"])
@dynamic_rate_limit()
def pull_raw(
	mailbox: str | None = None, limit: int = 50, last_received_at: str | None = None
) -> dict[str, list[str] | str]:
	"""Returns the raw emails for the given mailbox."""

	validate_user()
	validate_max_sync_limit(limit)

	result = []
	source = get_source()
	mailbox = mailbox or "inbox"
	last_received_at = convert_to_system_timezone(last_received_at)
	sync_history = get_mail_sync_history(source, frappe.session.user, get_account())
	result = get_raw_mails(mailbox, limit, last_received_at or sync_history.last_received_at)
	update_mail_sync_history(sync_history, result["last_received_at"], result["last_received_mail"])
	result["last_received_at"] = convert_to_utc(result["last_received_at"])

	return result


def validate_max_sync_limit(limit: int) -> None:
	"""Validates if the limit is within the maximum limit."""

	max_sync = cint(frappe.conf.max_email_sync_limit) or 100

	if limit > max_sync:
		frappe.throw(_("Cannot fetch more than {0} emails at a time.").format(max_sync))


def get_source() -> str:
	"""Returns the source of the request."""

	return frappe.request.headers.get("X-Site") or frappe.local.request_ip


def convert_to_system_timezone(last_received_at: str) -> datetime | None:
	"""Converts the last_received_at to system timezone."""

	if last_received_at:
		dt = datetime.fromisoformat(last_received_at)
		dt_utc = dt.astimezone(timezone.utc)
		return convert_utc_to_system_timezone(dt_utc)


def get_mails(
	mailbox: str, limit: int, last_received_at: str | datetime | None = None
) -> dict[str, list[dict] | str]:
	"""Returns the emails for the given mailbox."""

	account = get_account()
	mailbox_id = get_mailbox_id_by_role(account, mailbox, raise_exception=True)

	filter = {"inMailbox": mailbox_id}
	if last_received_at:
		dt = (
			last_received_at
			if isinstance(last_received_at, datetime)
			else datetime.fromisoformat(last_received_at)
		)
		dt_utc = dt.astimezone(timezone.utc)
		filter["after"] = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

	messages = fetch_messages(account, filter, limit=limit, sort_asc=True)
	last_received_at = messages[-1]["received_at"] if messages else now()
	last_received_mail = messages[-1]["name"] if messages else None

	for message in messages:
		for field in ["sent_at", "received_at"]:
			message[field] = convert_to_utc(message[field])

		for field in ["creation", "modified"]:
			message.pop(field, None)

	return {
		"mails": messages,
		"last_received_at": last_received_at,
		"last_received_mail": last_received_mail,
	}


def get_raw_mails(
	mailbox: str, limit: int, last_received_at: str | datetime | None = None
) -> dict[str, list[str] | str]:
	"""Returns the raw emails for the given mailbox."""

	result = get_mails(mailbox, limit, last_received_at)

	mails = []
	account = get_account()
	for messages in create_batch(result["mails"], 20):
		for _blob_id, blob in fetch_blobs(account, [message["blob_id"] for message in messages]).items():
			mails.append(blob.decode("utf-8"))

	result["mails"] = mails
	return result


def update_mail_sync_history(
	sync_history: "MailSyncHistory",
	last_received_at: str,
	last_received_mail: str | None = None,
) -> None:
	"""Update the last_received_at in the Mail Sync History."""

	kwargs = {
		"last_received_at": last_received_at or now(),
	}

	if last_received_mail:
		kwargs["last_received_mail"] = last_received_mail

	frappe.db.set_value(sync_history.doctype, sync_history.name, kwargs)
	frappe.db.commit()


def get_account() -> str:
	"""Returns the mail account for the current user."""

	user = frappe.session.user

	if account := get_account_for_user(user):
		return account

	frappe.throw(_("No Mail Account found for the user {0}.").format(frappe.bold(user)))
