import base64
from datetime import UTC, datetime, timezone
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.utils import cint, convert_utc_to_system_timezone, create_batch, now

from mail.api.auth import validate_user
from mail.client.doctype.mail_message.mail_message import fetch_blobs, fetch_messages
from mail.client.doctype.mail_sync_history.mail_sync_history import get_mail_sync_history
from mail.jmap import get_mailbox_id_by_role
from mail.utils import get_mail_config
from mail.utils.dt import convert_to_utc
from mail.utils.rate_limiter import dynamic_rate_limit

if TYPE_CHECKING:
	from mail.client.doctype.mail_sync_history.mail_sync_history import MailSyncHistory


@frappe.whitelist(methods=["GET"])
@dynamic_rate_limit()
def fetch_blob(blob_id: str, as_bytes: bool = False) -> str | bytes:
	"""Fetches the blob for the given blob_id."""

	validate_user()

	from mail.client.doctype.mail_message.mail_message import fetch_blob as _fetch_blob

	blob = _fetch_blob(frappe.session.user, blob_id)
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
	sync_history = get_mail_sync_history(source, frappe.session.user)
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
	sync_history = get_mail_sync_history(source, frappe.session.user)
	result = get_raw_mails(mailbox, limit, last_received_at or sync_history.last_received_at)
	update_mail_sync_history(sync_history, result["last_received_at"], result["last_received_mail"])
	result["last_received_at"] = convert_to_utc(result["last_received_at"])

	return result


def validate_max_sync_limit(limit: int) -> None:
	"""Validates if the limit is within the maximum limit."""

	max_sync = cint(get_mail_config("max_email_sync"))

	if limit > max_sync:
		frappe.throw(_("Cannot fetch more than {0} emails at a time.").format(max_sync))


def get_source() -> str:
	"""Returns the source of the request."""

	return frappe.request.headers.get("X-Site") or frappe.local.request_ip


def convert_to_system_timezone(last_received_at: str) -> datetime | None:
	"""Converts the last_received_at to system timezone."""

	if last_received_at:
		dt = datetime.fromisoformat(last_received_at)
		dt_utc = dt.astimezone(UTC)
		return convert_utc_to_system_timezone(dt_utc)


def get_mails(
	mailbox: str, limit: int, last_received_at: str | datetime | None = None
) -> dict[str, list[dict] | str]:
	"""Returns the emails for the given mailbox."""

	user = frappe.session.user
	mailbox_id = get_mailbox_id_by_role(user, mailbox, raise_exception=True)

	filter = {"inMailbox": mailbox_id}
	if last_received_at:
		dt = (
			last_received_at
			if isinstance(last_received_at, datetime)
			else datetime.fromisoformat(last_received_at)
		)
		dt_utc = dt.astimezone(UTC)
		filter["after"] = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

	sort = [{"property": "receivedAt", "isAscending": True}]
	messages, _total = fetch_messages(user, filter, limit=limit, sort=sort)
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
	for messages in create_batch(result["mails"], 20):
		for _blob_id, blob in fetch_blobs(
			frappe.session.user, [message["blob_id"] for message in messages]
		).items():
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
