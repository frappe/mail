import hashlib
from datetime import UTC, datetime

import frappe
import pydenticon
import requests
from frappe import _
from frappe.utils import format_datetime, random_string

from mail.api.contacts import create_contacts_if_not_exists
from mail.api.sieve import update_sieve_script_for_mailbox
from mail.client.doctype.mail_message.mail_message import (
	delete_messages,
	empty_mailbox,
	fetch_blob,
	fetch_thread,
	fetch_threads,
	get_message_ids,
	move_messages,
	search_messages,
	set_flagged_status,
	set_seen_status,
	set_spam_status,
)
from mail.client.doctype.mail_queue.mail_queue import MailQueue
from mail.client.doctype.mailbox.mailbox import add_mailbox, delete_mailboxes
from mail.client.doctype.mailbox_settings.mailbox_settings import set_mailbox_settings
from mail.jmap import get_email_service, get_mailbox_id_by_role
from mail.utils import convert_html_to_text, get_mail_config
from mail.utils.cache import get_user_emails
from mail.utils.user import has_role, is_jmap_configured
from mail.utils.validation import has_permission_for_user

AVATAR_CACHE_TTL = 60 * 60 * 24


@frappe.whitelist()
def get_mailboxes() -> list[dict]:
	"""Serializes and returns the user's mailboxes."""

	user = frappe.session.user
	if not is_jmap_configured(user):
		return []

	mailboxes = get_user_mailboxes(user)
	if not mailboxes:
		return []

	fields = ["id", "_name", "role", "total_threads", "unread_threads"]

	mailbox_settings = frappe.db.get_all(
		"Mailbox Settings",
		filters={"user": user, "mailbox_id": ["in", [m["id"] for m in mailboxes]]},
		fields=["mailbox_id", "icon", "color", "disable_push_notification"],
	)

	settings_map = {
		s.mailbox_id: {
			"icon": s.icon,
			"color": s.color,
			"disable_push_notification": s.disable_push_notification,
		}
		for s in mailbox_settings
	}

	result = []
	for mailbox in mailboxes:
		if mailbox["subscribed"] == 1:
			mailbox_data = {field: mailbox[field] for field in fields}
			mailbox_data.update(settings_map.get(mailbox["id"], {}))
			result.append(mailbox_data)

	return result


def get_user_mailboxes(user) -> list[dict]:
	"""Returns the user's mailboxes."""

	return frappe.get_all("Mailbox", filters={"user": user})


def get_avatar_url(email: str) -> str:
	"""Returns the avatar URL for the given email."""

	return f"/api/method/mail.api.mail.get_avatar?email={email}"


def add_user_images_to_emails(mails: list[dict], is_thread: bool = False) -> list[dict]:
	"""Append avatar URLs to the given list of emails."""

	if not mails:
		return mails

	email_map: dict[str, str] = {}
	rcpt_order = {"To": 0, "Cc": 1, "Bcc": 2}
	user_emails = {e.lower() for e in get_user_emails(frappe.session.user)}

	for mail in mails:
		name = mail["name"]
		if not name:
			continue

		from_email = (mail.get("from_email") or "").lower()

		if not from_email:
			continue

		selected_email = from_email

		if not is_thread and from_email in user_emails:
			recipients = sorted(mail["recipients"], key=lambda r: rcpt_order[r["type"] or 99])

			for rcpt in recipients:
				rcpt_email = (rcpt.get("email") or "").lower()
				if rcpt_email and rcpt_email not in user_emails:
					selected_email = rcpt_email
					break

		email_map[name] = selected_email

	unique_emails = {e for e in email_map.values() if e}

	user_image_map = {}
	if unique_emails:
		user_data = frappe.db.get_all(
			"User",
			filters={"name": ["in", list(unique_emails)]},
			fields=["name", "user_image"],
		)
		user_image_map = {u.name: u.user_image for u in user_data if u.user_image}

	images = {email: user_image_map.get(email) or get_avatar_url(email) for email in unique_emails}

	for mail in mails:
		email = email_map.get(mail["name"])
		mail["user_image"] = images.get(email) if email else None

	return mails


@frappe.whitelist()
def get_threads(mailbox: str, limit: int, filter_by: str | None = None) -> list:
	"""Returns threads from the selected mailbox for the current user."""

	user = frappe.session.user

	if mailbox == "starred":
		conditions = [
			{
				"inMailboxOtherThan": [
					get_mailbox_id_by_role(user, "junk", create_if_not_exists=True, raise_exception=True),
					get_mailbox_id_by_role(user, "trash", create_if_not_exists=True, raise_exception=True),
				]
			},
			{"someInThreadHaveKeyword": "$flagged"},
		]
	else:
		conditions = [{"inMailbox": mailbox}]

	filter_map = {
		"starred": {"someInThreadHaveKeyword": "$flagged"},
		"unread": {"notKeyword": "$seen"},
		"has_attachments": {"hasAttachment": True},
	}
	if filter_by in filter_map and not (mailbox == "starred" and filter_by == "starred"):
		conditions.append(filter_map[filter_by])

	if len(conditions) == 1:
		filter = conditions[0]
	else:
		filter = {"operator": "AND", "conditions": conditions}

	threads = [serialize_thread(t) for t in fetch_threads(user, filter, 0, limit)]

	return add_user_images_to_emails(threads, is_thread=False)


@frappe.whitelist()
def get_thread(thread_id: str) -> list[dict]:
	"""Returns mails for the given thread id."""

	mails = [serialize_mail(m) for m in fetch_thread(frappe.session.user, thread_id)]
	return add_user_images_to_emails(mails, is_thread=True)


@frappe.whitelist()
def get_attachment(user: str, blob_id: str, filename: str | None = None) -> None:
	"""Fetches and returns the attachment."""

	if not user:
		frappe.throw(_("User is required."))

	if not blob_id:
		frappe.throw(_("Blob ID is required."))

	content = fetch_blob(user, blob_id, filename)

	frappe.local.response.filename = filename or blob_id
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"


def serialize_thread(thread: dict) -> dict:
	"""Serializes thread for response."""

	thread_fields = [
		"name",
		"user",
		"thread_id",
		"mailboxes",
		"from_name",
		"from_email",
		"subject",
		"received_at",
		"recipients",
		"seen",
		"draft",
		"junk",
		"flagged",
		"preview",
	]
	return {
		**{field: thread[field] for field in thread_fields},
		"attachments": serialize_attachments(thread.get("attachments", [])),
	}


def serialize_mail(mail: dict) -> dict:
	"""Serializes mail for response."""

	mail_fields = [
		"name",
		"message_id",
		"id",
		"from_name",
		"from_email",
		"subject",
		"html_body",
		"text_body",
		"preview",
		"received_at",
		"draft",
		"seen",
		"junk",
		"flagged",
		"mailboxes",
		"recipients",
		"reply_to",
	]

	return {
		**{field: mail[field] for field in mail_fields},
		"attachments": serialize_attachments(mail.get("attachments", [])),
	}


def serialize_attachments(attachments: list[dict]) -> list[dict]:
	"""Serializes attachment for response."""

	attachment_fields = ["filename", "type", "size", "blob_id", "disposition", "cid", "url"]

	return [
		{field: attachment[field] for field in attachment_fields}
		for attachment in attachments
		if attachment.get("filename")
	]


@frappe.whitelist()
def fetch_attachment(blob_id: str) -> bytes:
	"""Returns the content of an attachment."""

	return fetch_blob(frappe.session.user, blob_id)


@frappe.whitelist()
def create_mail(
	from_email: str,
	to: list[str],
	cc: list[str],
	bcc: list[str],
	subject: str | None,
	html_body: str | None,
	from_name: str = "",
	attachments: list[dict] | None = None,
	in_reply_to: str | None = None,
	in_reply_to_id: str | None = None,
	forwarded_from_id: str | None = None,
	save_as_draft: bool = False,
) -> dict:
	"""Creates new mail queue."""

	doc_attachments = []
	for d in attachments:
		cid = d.get("cid") or random_string(10)
		doc_attachments.append(
			{
				"file_url": d.get("file_url", ""),
				"blob_id": d.get("blob_id", ""),
				"filename": d.get("file_name") or d.get("filename", ""),
				"type": d.get("type", ""),
				"size": d.get("size", ""),
				"disposition": d.get("disposition"),
				"cid": cid,
			}
		)

	recipients = [{"type": "To", "email": email} for email in to]
	recipients += [{"type": "Cc", "email": email} for email in cc]
	recipients += [{"type": "Bcc", "email": email} for email in bcc]

	doc = MailQueue._create(
		user=frappe.session.user,
		from_email=from_email,
		from_name=from_name,
		subject=subject,
		html_body=html_body,
		in_reply_to=in_reply_to,
		in_reply_to_id=in_reply_to_id,
		forwarded_from_id=forwarded_from_id,
		attachments=doc_attachments,
		recipients=recipients,
		save_as_draft=save_as_draft,
	)

	if not save_as_draft and doc.status == "Submitted":
		create_contacts_if_not_exists(doc.recipients)

	return {"id": doc.id, "status": doc.status, "error": doc.error_message}


@frappe.whitelist()
def update_draft_mail(
	id: str,
	from_email: str,
	to: list[str],
	cc: list[str],
	bcc: list[str],
	subject: str | None,
	html_body: str | None,
	from_name: str = "",
	attachments: list[dict] | None = None,
	submit: bool = False,
) -> dict:
	"""Creates new mail queue from existing draft message."""

	doc = frappe.get_doc("Mail Message", f"{frappe.session.user}|{id}")
	doc.check_permission(permtype="write")

	doc.from_email = from_email
	doc.from_name = from_name
	doc.subject = subject

	_attachments = {a.cid: a for a in doc.attachments if a.cid}
	doc.attachments = []

	for d in attachments or []:
		if file_url := d.get("file_url"):
			doc.append(
				"attachments",
				{
					"file_url": file_url,
					"filename": d.get("filename", ""),
					"disposition": d.get("disposition"),
					"cid": d.get("cid") or random_string(10),
				},
			)
		else:
			existing_attachment = _attachments.get(d["cid"])
			if not existing_attachment:
				frappe.throw(_("Attachment with cid {0} not found in the current draft.").format(d["cid"]))

			doc.append(
				"attachments",
				{
					"blob_id": existing_attachment.blob_id,
					"type": existing_attachment.type,
					"size": existing_attachment.size,
					"filename": existing_attachment.filename,
					"disposition": existing_attachment.disposition,
					"cid": d["cid"],
				},
			)

	doc.html_body = html_body
	doc.text_body = convert_html_to_text(doc.html_body)

	doc.recipients = []
	for email in to:
		doc.append("recipients", {"type": "To", "email": email})
	for email in cc:
		doc.append("recipients", {"type": "Cc", "email": email})
	for email in bcc:
		doc.append("recipients", {"type": "Bcc", "email": email})

	new_doc = doc.submit() if submit else doc.save_draft()

	if submit and new_doc.status == "Submitted":
		create_contacts_if_not_exists(doc.recipients)

	return {"id": new_doc.id, "status": new_doc.status, "error": new_doc.error_message}


@frappe.whitelist()
def delete_mail(id: str) -> None:
	"""Deletes the given mail."""

	delete_messages(frappe.session.user, [id])


@frappe.whitelist()
def get_mime_message(name: str) -> dict:
	"""Fetches mail mime message and related data."""

	doc = frappe.get_doc("Mail Message", name)
	doc.check_permission(permtype="read")

	def get_mail_recipients(recipient_type):
		return ", ".join([d.email for d in doc.recipients if d.type == recipient_type])

	pass_or_fail = {1: _("'Pass'"), 0: _("'Fail'")}

	result = {
		"message": doc.message or doc.get_mime_message(),
		"message_id": {"label": _("Message ID"), "value": doc.message_id},
		"created_at": {
			"label": _("Created at"),
			"value": _("{0} (Delivered after {1} seconds)").format(
				format_datetime(doc.sent_at, "E, MMM d, yyyy 'at' h:mm a"),
				round(doc.received_after),
			),
		},
		"subject": {"label": _("Subject"), "value": doc.subject},
		"from": {"label": _("From"), "value": f"{doc.from_name} <{doc.from_email}>"},
		"to": {"label": _("To"), "value": get_mail_recipients("To")},
		"cc": {"label": _("CC"), "value": get_mail_recipients("Cc")},
		"bcc": {"label": _("BCC"), "value": get_mail_recipients("Bcc")},
	}

	if doc.spf_description:
		result["spf"] = {
			"label": _("SPF"),
			"value": _("{0} with IP {1}").format(pass_or_fail[doc.spf_pass], doc.from_ip),
		}
	if doc.dkim_description:
		result["dkim"] = {"label": _("DKIM"), "value": pass_or_fail[doc.dkim_pass]}
	if doc.dmarc_description:
		result["dmarc"] = {"label": _("DMARC"), "value": pass_or_fail[doc.dmarc_pass]}

	return result


def get_user_and_filtered_message_ids(
	thread_ids: list[str], mailbox: str | None = None
) -> tuple[str, list[str]]:
	"""Gets user and filtered message IDs for the given mailbox."""

	user = frappe.session.user
	if mailbox == "starred":
		mailbox = [d["id"] for d in get_user_mailboxes(user) if d["role"] != "trash"]
	elif mailbox == "search":
		mailbox = None
	messages = get_message_ids(user, thread_ids, mailbox)

	return user, messages


@frappe.whitelist()
def set_seen(thread_ids: dict[bool, list[str]], mailbox: str) -> dict:
	"""Sets seen for threads."""

	for is_seen, ids in thread_ids.items():
		user, messages = get_user_and_filtered_message_ids(ids, mailbox)
		set_seen_status(user, messages, is_seen)

	return thread_ids


@frappe.whitelist()
def set_flagged(ids: list[str], flagged: bool) -> dict:
	"""Sets flagged for mails."""

	set_flagged_status(frappe.session.user, ids, flagged)

	return {"ids": ids, "flagged": flagged}


@frappe.whitelist()
def move_mails(ids: list[str], mailbox: str) -> None:
	"""Sets mailbox for mails."""

	move_messages(frappe.session.user, ids, mailbox)


@frappe.whitelist()
def set_threads_mailbox(thread_ids: dict[str, list[str]]) -> dict:
	"""Sets mailbox for threads."""

	for move_to_mailbox, ids in thread_ids.items():
		user, messages = get_user_and_filtered_message_ids(ids)
		move_messages(user, messages, move_to_mailbox)

	return thread_ids


@frappe.whitelist()
def set_mails_spam_status(ids: list[str], spam: bool) -> list[str]:
	"""Sets spam status of the given mails."""

	set_spam_status(frappe.session.user, ids, spam)

	return ids


@frappe.whitelist()
def set_threads_spam_status(thread_ids: dict[bool, list[str]]) -> dict:
	"""Sets spam status for the mails belonging to the given threads."""

	for is_spam, ids in thread_ids.items():
		user, messages = get_user_and_filtered_message_ids(ids)
		set_spam_status(user, messages, is_spam)

	return thread_ids


@frappe.whitelist()
def delete_threads(thread_ids: list[str], mailbox: str) -> list[str]:
	"""Deletes mails belonging to the given threads."""

	user, messages = get_user_and_filtered_message_ids(thread_ids, mailbox)
	delete_messages(user, messages)

	return thread_ids


@frappe.whitelist()
def empty_user_mailbox(mailbox: str) -> None:
	"""Empties the given mailbox."""

	empty_mailbox(frappe.session.user, mailbox)


@frappe.whitelist()
def search_mails(filter: dict | None = None, limit: int = 5) -> tuple[list[dict], int]:
	"""Returns search results for the given query."""

	if not filter:
		return ([], 0)

	normalized_filter = normalize_filter(filter)
	mails, total = search_messages(frappe.session.user, normalized_filter, limit=limit)

	return add_user_images_to_emails(mails), total


def normalize_filter(filter: dict) -> dict:
	"""Normalize and transform filter parameters for email search."""

	filter = filter.copy()

	if filter.get("hasAttachment") in ["true", "false"]:
		filter["hasAttachment"] = filter["hasAttachment"] == "true"

	if filter.get("isRead"):
		key = "hasKeyword" if filter["isRead"] == "true" else "notKeyword"
		filter[key] = "$seen"
		del filter["isRead"]

	for date_key in ["after", "before"]:
		if filter.get(date_key):
			filter[date_key] = parse_date_to_utc_iso(filter[date_key])

	return {"operator": "AND", "conditions": [{k: v} for k, v in filter.items()]}


def parse_date_to_utc_iso(date_str: str) -> str:
	"""Parse date string and convert to ISO format with UTC timezone."""
	return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC).isoformat()


@frappe.whitelist()
def get_avatar(email: str, size: int = 128, strict: bool = False) -> None:
	"""Fetch and return avatar for the given email."""

	if not email:
		frappe.throw(_("Email is required to fetch avatar."))

	email = email.strip().lower()
	email_hash = hashlib.md5(email.encode()).hexdigest()

	cache_key = f"avatar:{email_hash}:{size}"

	# 1. Try cache
	avatar = frappe.cache.get_value(cache_key)

	if not avatar:
		# 2. Try Gravatar
		default = get_mail_config("gravatar_default_avatar")
		try:
			res = requests.get(
				f"https://secure.gravatar.com/avatar/{email_hash}",
				params={"d": default, "s": size},
				timeout=3,
			)
			if res.ok:
				avatar = res.content
		except requests.RequestException:
			pass

		# 3. Handle missing gravatar
		if not avatar:
			if strict:
				frappe.throw(_("Avatar not found."), frappe.DoesNotExistError)

			generator = pydenticon.Generator(
				5,
				5,
				foreground=[
					"#1abc9c",
					"#2ecc71",
					"#3498db",
					"#9b59b6",
					"#e74c3c",
				],
				background="#ffffff",
			)
			avatar = generator.generate(email_hash, size, size, output_format="png")

		# Cache the avatar for future requests
		frappe.cache.set_value(cache_key, avatar, expires_in_sec=AVATAR_CACHE_TTL)

	frappe.local.response.filename = f"{email_hash}.png"
	frappe.local.response.filecontent = avatar
	frappe.local.response.mimetype = "image/png"
	frappe.local.response.type = "binary"


def get_email_suggestions(query: str, limit: int = 5) -> list[str]:
	"""Returns email suggestions based on the given query."""

	if not query:
		return []

	user = frappe.session.user
	has_permission_for_user(user)

	service = get_email_service(frappe.session.user)
	return service.get_email_suggestions(query, limit)


@frappe.whitelist()
def create_mailbox(
	name: str,
	parent: str | None = None,
	icon: str | None = None,
	color: str | None = None,
	disable_push_notification: bool = False,
	automation_rules: dict | None = None,
) -> str:
	"""Creates a new mailbox and initializes its settings for the current user."""

	user = frappe.session.user
	mailbox_id = add_mailbox(user, name, None, parent)

	set_mailbox_settings(
		user,
		mailbox_id,
		icon=icon,
		color=color,
		disable_push_notification=disable_push_notification,
	)

	update_sieve_script_for_mailbox(name, automation_rules)


@frappe.whitelist()
def update_mailbox(
	id: str,
	name: str,
	old_name: str,
	role: str | None = None,
	parent: str | None = None,
	icon: str | None = None,
	color: str | None = None,
	disable_push_notification: bool = False,
	automation_rules: dict | None = None,
) -> None:
	"""Updates Mailbox Settings for the given mailbox ID."""

	set_mailbox_settings(
		frappe.session.user,
		id,
		_name=name,
		role=role,
		parent=parent,
		icon=icon,
		color=color,
		disable_push_notification=disable_push_notification,
	)

	update_sieve_script_for_mailbox(name, automation_rules, old_name)


@frappe.whitelist()
def delete_mailbox(id: str, name: str) -> None:
	"""Deletes the mailbox with the given mailbox ID, followed by its settings."""

	user = frappe.session.user
	delete_mailboxes(user, [id])
	update_sieve_script_for_mailbox(name)
	frappe.db.delete("Mailbox Settings", {"user": user, "mailbox_id": id})
