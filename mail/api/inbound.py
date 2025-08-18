import base64
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.utils import convert_utc_to_system_timezone, now

from mail.api.auth import validate_user
from mail.mail.doctype.mail_sync_history.mail_sync_history import get_mail_sync_history
from mail.utils.cache import get_account_for_user
from mail.utils.dt import convert_to_utc
from mail.utils.rate_limiter import dynamic_rate_limit

if TYPE_CHECKING:
	from mail.mail.doctype.mail_sync_history.mail_sync_history import MailSyncHistory

MAX_SYNC = 100


@frappe.whitelist(methods=["GET"])
@dynamic_rate_limit()
def fetch_blob(blob_id: str, as_bytes: bool = False) -> str | bytes:
	"""Fetches the blob for the given blob_id."""

	validate_user()
	blob = _fetch_blob(blob_id)
	return blob if as_bytes else base64.b64encode(blob).decode("utf-8")


@frappe.whitelist(methods=["GET"])
@dynamic_rate_limit()
def pull(
	folders: list[str] | None = None, limit: int = 50, last_synced_at: str | None = None
) -> dict[str, list[dict] | str]:
	"""Returns the emails for the given folders."""

	validate_user()
	validate_max_sync_limit(limit)

	result = []
	source = get_source()
	folders = folders or ["Inbox"]
	last_synced_at = convert_to_system_timezone(last_synced_at)
	sync_history = get_mail_sync_history(source, frappe.session.user, get_account())
	result = get_mails(folders, limit, last_synced_at or sync_history.last_synced_at)
	update_mail_sync_history(sync_history, result["last_synced_at"], result["last_synced_mail"])
	result["last_synced_at"] = convert_to_utc(result["last_synced_at"])

	return result


@frappe.whitelist(methods=["GET"])
@dynamic_rate_limit()
def pull_raw(
	folders: list[str] | None = None, limit: int = 50, last_synced_at: str | None = None
) -> dict[str, list[str] | str]:
	"""Returns the raw emails for the given folders."""

	validate_user()
	validate_max_sync_limit(limit)

	result = []
	source = get_source()
	folders = folders or ["Inbox"]
	last_synced_at = convert_to_system_timezone(last_synced_at)
	sync_history = get_mail_sync_history(source, frappe.session.user, get_account())
	result = get_raw_mails(folders, limit, last_synced_at or sync_history.last_synced_at)
	update_mail_sync_history(sync_history, result["last_synced_at"], result["last_synced_mail"])
	result["last_synced_at"] = convert_to_utc(result["last_synced_at"])

	return result


def _fetch_blob(blob_id: str) -> bytes:
	"""Fetches the blob for the given blob_id."""

	from mail.mail.doctype.mail_message.mail_message import fetch_blob

	return fetch_blob(get_account(), blob_id)


def validate_max_sync_limit(limit: int) -> None:
	"""Validates if the limit is within the maximum limit."""

	if limit > MAX_SYNC:
		frappe.throw(_("Cannot fetch more than {0} emails at a time.").format(MAX_SYNC))


def get_source() -> str:
	"""Returns the source of the request."""

	return frappe.request.headers.get("X-Site") or frappe.local.request_ip


def convert_to_system_timezone(last_synced_at: str) -> datetime | None:
	"""Converts the last_synced_at to system timezone."""

	if last_synced_at:
		dt = datetime.fromisoformat(last_synced_at)
		dt_utc = dt.astimezone(timezone.utc)
		return convert_utc_to_system_timezone(dt_utc)


def get_mails(folders: list, limit: int, last_synced_at: str | None = None) -> dict[str, list[dict] | str]:
	"""Returns the emails for the given folders."""

	account = get_account()

	EM = frappe.qb.DocType("Email Message")
	EMR = frappe.qb.DocType("Email Message Recipient")
	ERT = frappe.qb.DocType("Email Message Reply To")

	query = (
		frappe.qb.from_(EM)
		.left_join(EMR)
		.on(EM.name == EMR.parent)
		.left_join(ERT)
		.on(EM.name == ERT.parent)
		.select(
			EM.name.as_("id"),
			EM.folder,
			EM.from_name,
			EM.from_email,
			EM.subject,
			EM.html_body,
			EM.text_body,
			EM.message_id,
			EM.blob_id,
			EM.size,
			EM.has_attachment,
			EM.sent_at,
			EM.received_at,
			EM.thread_id,
			EM.creation,
			EMR.type.as_("recipient_type"),
			EMR.display_name.as_("recipient_name"),
			EMR.email.as_("recipient_email"),
			ERT.display_name.as_("reply_to_name"),
			ERT.email.as_("reply_to_email"),
		)
		.where((EM.draft == 0) & (EM.destroyed == 0) & (EM.account == account) & (EM.folder.isin(folders)))
		.orderby(EM.creation)
		.limit(limit)
	)

	if last_synced_at:
		query = query.where(EM.creation > last_synced_at)

	messages = query.run(as_dict=True)
	last_synced_at = messages[-1]["creation"] if messages else now()
	last_synced_mail = messages[-1]["id"] if messages else None

	grouped_messages = {}
	messages_with_attachment = set()
	for message in messages:
		id = message["id"]
		if id not in grouped_messages:
			grouped_messages[id] = {
				"id": id,
				"folder": message["folder"],
				"from": {"name": message["from_name"], "email": message["from_email"]},
				"subject": message["subject"],
				"html_body": message["html_body"],
				"text_body": message["text_body"],
				"message_id": message["message_id"],
				"blob_id": message["blob_id"],
				"size": message["size"],
				"has_attachment": message["has_attachment"],
				"sent_at": convert_to_utc(message["sent_at"]),
				"received_at": convert_to_utc(message["received_at"]),
				"thread_id": message["thread_id"],
				"recipients": defaultdict(list),
				"reply_to": [],
				"attachments": [],
			}

			if message["has_attachment"]:
				messages_with_attachment.add(id)

		if recipient_email := message["recipient_email"]:
			recipient = {"name": message["recipient_name"], "email": recipient_email}
			grouped_messages[id]["recipients"][message["recipient_type"]].append(recipient)

		if reply_to_email := message["reply_to_email"]:
			reply_to = {"name": message["reply_to_name"], "email": reply_to_email}
			grouped_messages[id]["reply_to"].append(reply_to)

	messages = list(grouped_messages.values())

	if messages_with_attachment:
		PART = frappe.qb.DocType("Email Message Part")
		attachments = (
			frappe.qb.from_(PART)
			.select(
				PART.parent,
				PART.filename,
				PART.type,
				PART.size,
				PART.disposition,
				PART.blob_id,
			)
			.where(
				(PART.parenttype == "Email Message")
				& (PART.parentfield == "attachments")
				& (PART.parent.isin(messages_with_attachment))
			)
		).run(as_dict=True)

		attachments_map = defaultdict(list)
		for a in attachments:
			if not a.filename:
				if a.type == "message/delivery-status":
					a.filename = "Delivery Report"
				elif a.type == "message/rfc822":
					a.filename = "Original Message"
			attachments_map[a.pop("parent")].append(a)

		if attachments_map:
			for message in messages:
				if message["has_attachment"]:
					message["attachments"] = attachments_map.get(message["id"], [])

	return {
		"mails": messages,
		"last_synced_at": last_synced_at,
		"last_synced_mail": last_synced_mail,
	}


def get_raw_mails(folders: list, limit: int, last_synced_at: str | None = None) -> dict[str, list[str] | str]:
	"""Returns the raw incoming mails for the given email address."""

	account = get_account()

	EM = frappe.qb.DocType("Email Message")
	query = (
		frappe.qb.from_(EM)
		.select(EM.name.as_("id"), EM.blob_id, EM.creation)
		.where((EM.draft == 0) & (EM.destroyed == 0) & (EM.account == account) & (EM.folder.isin(folders)))
		.orderby(EM.creation)
		.limit(limit)
	)

	if last_synced_at:
		query = query.where(EM.creation > last_synced_at)

	messages = query.run(as_dict=True)
	last_synced_at = messages[-1]["creation"] if messages else now()
	last_synced_mail = messages[-1]["id"] if messages else None

	mails = []
	for message in messages:
		blob = _fetch_blob(message["blob_id"])
		mails.append(blob.decode("utf-8"))

	return {
		"mails": mails,
		"last_synced_at": last_synced_at,
		"last_synced_mail": last_synced_mail,
	}


def update_mail_sync_history(
	sync_history: "MailSyncHistory",
	last_synced_at: str,
	last_synced_mail: str | None = None,
) -> None:
	"""Update the last_synced_at in the Mail Sync History."""

	kwargs = {
		"last_synced_at": last_synced_at or now(),
	}

	if last_synced_mail:
		kwargs["last_synced_mail"] = last_synced_mail

	frappe.db.set_value(sync_history.doctype, sync_history.name, kwargs)
	frappe.db.commit()


def get_account() -> str:
	"""Returns the mail account for the current user."""

	user = frappe.session.user

	if account := get_account_for_user(user):
		return account

	frappe.throw(_("No Mail Account found for the user {0}.").format(frappe.bold(user)))
