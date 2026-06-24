import hashlib
import io
import os
import zipfile
from datetime import UTC, datetime

import frappe
import pydenticon
import requests
from frappe import _
from frappe.model.document import bulk_insert
from frappe.utils import format_datetime, random_string

from mail.api.contacts import create_contacts_if_not_exists
from mail.api.sieve import (
	SCREENING_MAILBOX_NAME,
	update_sieve_script_for_mailbox,
	update_sieve_script_for_screened_emails,
)
from mail.api.utils import get_avatar_url
from mail.client.doctype.mail_message.mail_message import (
	add_messages_to_mailbox,
	delete_messages,
	empty_mailbox,
	fetch_blob,
	fetch_blobs,
	fetch_thread,
	fetch_threads,
	get_messages,
	move_messages_to_mailbox,
	remove_messages_from_mailbox,
	search_messages,
	set_flagged_status,
	set_messages_mailboxes,
	set_seen_status,
	set_spam_status,
)
from mail.client.doctype.mail_queue.mail_queue import MailQueue
from mail.client.doctype.mailbox.mailbox import add_mailbox, delete_mailboxes
from mail.client.doctype.mailbox_settings.mailbox_settings import set_mailbox_settings
from mail.client.doctype.screened_email_address.screened_email_address import (
	get_screened_email_addresses,
)
from mail.jmap import (
	get_email_service,
	get_mailbox_id_by_name,
	get_mailbox_id_by_role,
	parse_account,
)
from mail.utils import convert_html_to_text, get_config, log_error
from mail.utils.user import get_account_emails, is_jmap_configured
from mail.utils.validation import has_permission_for_user

AVATAR_CACHE_TTL = 60 * 60 * 24


@frappe.whitelist()
def get_mailboxes(account: str) -> list[dict]:
	"""Serializes and returns the user's mailboxes."""

	user = frappe.session.user
	if not is_jmap_configured(user):
		return []

	mailboxes = get_user_mailboxes(account)
	if not mailboxes:
		return []

	fields = ["name", "id", "_name", "role", "total_threads", "unread_threads", "subscribed"]

	mailbox_settings = frappe.db.get_all(
		"Mailbox Settings",
		filters={"account": account, "mailbox_id": ["in", [m["id"] for m in mailboxes]]},
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
		mailbox_data = {field: mailbox[field] for field in fields}
		mailbox_data.update(settings_map.get(mailbox["id"], {}))
		result.append(mailbox_data)

	return result


def get_user_mailboxes(account: str) -> list[dict]:
	"""Returns the user's mailboxes."""

	return frappe.get_all("Mailbox", filters={"account": account})


def add_user_images_to_emails(account: str, mails: list[dict], is_thread: bool = False) -> list[dict]:
	"""Append avatar URLs to the given list of emails."""

	if not mails:
		return mails

	email_map: dict[str, str] = {}
	rcpt_order = {"To": 0, "Cc": 1, "Bcc": 2}
	user_emails = {e.lower() for e in get_account_emails(account)}

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
def get_threads(account: str, mailbox: str, limit: int, start: int = 0, filter_by: str | None = None) -> list:
	"""Returns a page of threads from the selected mailbox for the account."""

	if mailbox == "starred":
		conditions = [
			{
				"inMailboxOtherThan": [
					get_mailbox_id_by_role(account, "junk", create_if_not_exists=True, raise_exception=True),
					get_mailbox_id_by_role(account, "trash", create_if_not_exists=True, raise_exception=True),
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

	conversations = fetch_threads(account, filter, start, limit)

	sent_mailbox = get_mailbox_id_by_role(account, "sent")

	threads = []
	for conversation in conversations.values():
		if not conversation:
			continue

		# The summary row is derived from the thread's messages in the current mailbox (falling back
		# to the whole conversation for cross-mailbox views like "starred").
		in_mailbox = [
			m for m in conversation if any(mb["mailbox_id"] == mailbox for mb in m["mailboxes"])
		] or conversation

		# The preview/date reflect the latest message in the whole conversation (the most recent
		# activity) everywhere except Sent, where the latest sent message is shown.
		latest = in_mailbox[-1] if mailbox == sent_mailbox else conversation[-1]
		threads.append(serialize_thread(in_mailbox, conversation, latest))

	# Avatars for the list-view summary rows, and for each message in the nested threads.
	add_user_images_to_emails(account, threads, is_thread=False)
	add_user_images_to_emails(account, [m for thread in threads for m in thread["messages"]], is_thread=True)

	return threads, mailbox


@frappe.whitelist()
def get_thread(account: str, thread_id: str) -> list[dict]:
	"""Returns the full list of messages in a thread, for threads not present in the mailbox list
	(e.g. search results or a thread on another page)."""

	mails = [serialize_mail(m) for m in fetch_thread(account, thread_id)]
	return add_user_images_to_emails(account, mails, is_thread=True)


@frappe.whitelist()
def get_attachment(account: str, blob_id: str, filename: str | None = None) -> None:
	"""Fetches and returns the attachment."""

	if not blob_id:
		frappe.throw(_("Blob ID is required."))

	content = fetch_blob(account, blob_id, filename)

	frappe.local.response.filename = filename or blob_id
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"


def serialize_thread(messages: list[dict], thread_messages: list[dict], latest: dict | None = None) -> dict:
	"""Serializes a thread for response.

	Both `messages` (the thread's messages within the current mailbox) and `thread_messages` (the full
	conversation across all mailboxes) are expected ordered oldest to newest. The list-view summary
	fields are derived from `latest` (defaulting to the latest of `messages`), except `subject` which
	comes from the conversation's first message (the thread's original subject); the full conversation
	is serialized under `messages` so the whole thread can be rendered without a separate fetch.
	"""

	first = thread_messages[0]
	latest = latest or messages[-1]

	thread_fields = [
		"name",
		"account",
		"id",
		"thread_id",
		"mailboxes",
		"from_name",
		"from_email",
		"received_at",
		"recipients",
		"seen",
		"draft",
		"junk",
		"flagged",
		"preview",
	]
	return {
		**{field: latest[field] for field in thread_fields},
		"subject": first["subject"],
		"attachments": serialize_attachments(latest.get("attachments", [])),
		"messages": [serialize_mail(message) for message in thread_messages],
	}


def serialize_mail(mail: dict) -> dict:
	"""Serializes mail for response."""

	mail_fields = [
		"name",
		"message_id",
		"id",
		"thread_id",
		"from_name",
		"from_email",
		"subject",
		"html_body",
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

	# text_body is only rendered as a fallback when html_body is empty (the UI renders
	# `html_body || text_body`), so omit the redundant copy whenever there's HTML.
	html = mail.get("html_body") or ""
	return {
		**{field: mail[field] for field in mail_fields},
		"text_body": "" if html else mail.get("text_body", ""),
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
def fetch_attachment(account: str, blob_id: str) -> bytes:
	"""Returns the content of an attachment."""

	return fetch_blob(account, blob_id)


@frappe.whitelist()
def fetch_attachments_as_zip(account: str, attachments: list[dict] | str) -> bytes:
	"""Returns the provided attachments bundled into a ZIP archive."""

	if isinstance(attachments, str):
		attachments = frappe.parse_json(attachments)

	attachments = [a for a in (attachments or []) if a.get("blob_id")]
	if not attachments:
		frappe.throw(_("No attachments to download."))

	blobs = [(a["blob_id"], a.get("filename")) for a in attachments]
	contents = fetch_blobs(account, blobs)

	buffer = io.BytesIO()
	used_names = {}
	with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
		for attachment in attachments:
			content = contents.get(attachment["blob_id"])
			if content is None:
				continue

			filename = _get_unique_filename(attachment.get("filename") or "attachment", used_names)
			zf.writestr(filename, content)

	return buffer.getvalue()


def _get_unique_filename(filename: str, used_names: dict[str, int]) -> str:
	"""Returns a unique filename, appending a counter to duplicates (e.g. "file (1).pdf")."""

	if filename not in used_names:
		used_names[filename] = 0
		return filename

	used_names[filename] += 1
	name, ext = os.path.splitext(filename)
	return f"{name} ({used_names[filename]}){ext}"


@frappe.whitelist()
def fetch_mail_as_eml(name: str) -> bytes:
	"""Returns the MIME message content of the mail as bytes for EML download."""

	doc = frappe.get_doc("Mail Message", name)
	doc.check_permission(permtype="read")

	content = doc.message or doc.get_mime_message()
	if isinstance(content, str):
		return content.encode("utf-8")
	return content


@frappe.whitelist()
def create_mail(
	account: str,
	from_email: str,
	to: list[dict],
	cc: list[dict],
	bcc: list[dict],
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

	recipients = []
	for type, emails in [("To", to), ("Cc", cc), ("Bcc", bcc)]:
		recipients += [
			{"type": type, "email": email.get("email"), "display_name": email.get("display_name")}
			for email in emails
		]

	doc = MailQueue._create(
		account=account,
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
		create_contacts_if_not_exists(account, doc.recipients)
		auto_accept_recipients(account, doc.recipients)

	return {"id": doc.id, "status": doc.status, "error": doc.error_message, "thread_id": doc.thread_id}


@frappe.whitelist()
def update_draft_mail(
	account: str,
	id: str,
	from_email: str,
	to: list[dict],
	cc: list[dict],
	bcc: list[dict],
	subject: str | None,
	html_body: str | None,
	from_name: str = "",
	attachments: list[dict] | None = None,
	submit: bool = False,
) -> dict:
	"""Creates new mail queue from existing draft message."""

	doc = frappe.get_doc("Mail Message", f"{account}|{id}")
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
	for type, emails in [("To", to), ("Cc", cc), ("Bcc", bcc)]:
		for email in emails:
			doc.append(
				"recipients",
				{"type": type, "email": email.get("email"), "display_name": email.get("display_name")},
			)

	new_doc = doc.submit() if submit else doc.save_draft()

	if submit and new_doc.status == "Submitted":
		create_contacts_if_not_exists(account, doc.recipients)
		auto_accept_recipients(account, doc.recipients)

	return {
		"id": new_doc.id,
		"status": new_doc.status,
		"error": new_doc.error_message,
		"thread_id": new_doc.thread_id,
	}


@frappe.whitelist()
def delete_mail(account: str, id: str) -> None:
	"""Deletes the given mail."""

	delete_messages(account, [id])


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


@frappe.whitelist()
def set_flagged(account: str, ids: list[str], flagged: bool) -> dict:
	"""Sets flagged for mails."""

	set_flagged_status(account, ids, flagged)

	return {"ids": ids, "flagged": flagged}


@frappe.whitelist()
def set_mails_seen(account: str, ids: list[str], seen: bool) -> list[str]:
	"""Sets seen status for the given mails."""

	set_seen_status(account, ids, seen)

	return ids


@frappe.whitelist()
def move_mails(account: str, ids: list[str], mailbox: str, clear_junk: bool = False) -> None:
	"""Sets mailbox for mails."""

	if clear_junk:
		set_spam_status(account, ids, spam=False)
	move_messages_to_mailbox(account, ids, mailbox)


@frappe.whitelist()
def add_mails_to_mailbox(account: str, ids: list[str], mailbox_id: str) -> None:
	"""Adds mails to a mailbox without removing them from their existing mailboxes."""

	add_messages_to_mailbox(account, ids, mailbox_id)


@frappe.whitelist()
def remove_mails_from_mailbox(account: str, ids: list[str], mailbox_id: str) -> None:
	"""Removes mails from a mailbox without deleting them."""

	remove_messages_from_mailbox(account, ids, mailbox_id)


def _screen_senders(account: str, ids: list[str], action: str | None) -> None:
	"""Screen the senders of the given mails with `action` (Spam/Accepted/Reject), in the same request as
	the mail change — so marking junk/not-junk (and undoing it) updates the sender's rule atomically."""

	if not action:
		return

	from_emails = [m["from_email"] for m in get_messages(account, ids) if m.get("from_email")]
	if from_emails:
		screen_email_addresses(account, from_emails, action=action)


@frappe.whitelist()
def set_mails_mailboxes(account: str, mails: list[dict], screen_action: str | None = None) -> None:
	"""Restores each mail's exact mailbox membership and junk status (used to undo a move), optionally
	re-screening the senders with `screen_action` to reverse a junk/not-junk's screening on undo."""

	set_messages_mailboxes(account, mails)
	_screen_senders(account, [m["id"] for m in mails], screen_action)


@frappe.whitelist()
def set_mails_spam_status(
	account: str, ids: list[str], spam: bool, screen_action: str | None = None
) -> list[str]:
	"""Sets spam status of the given mails, optionally screening their senders with `screen_action`
	(Spam on Junk, Accepted on Not Junk) in the same call."""

	set_spam_status(account, ids, spam)
	_screen_senders(account, ids, screen_action)

	return ids


@frappe.whitelist()
def empty_user_mailbox(account: str, mailbox: str) -> None:
	"""Empties the given mailbox."""

	empty_mailbox(account, mailbox)


@frappe.whitelist()
def search_mails(
	account: str, filter: dict | None = None, limit: int = 5, start: int = 0
) -> tuple[list[dict], int]:
	"""Returns search results for the given query."""

	if not filter:
		return ([], 0)

	normalized_filter = normalize_filter(filter)
	mails, total = search_messages(account, normalized_filter, position=start, limit=limit)

	return add_user_images_to_emails(account, mails), total


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
		# 2. Try Gravatar (opt-in: avoids leaking emails to a third party when disabled)
		if get_config("enable_gravatar"):
			default = get_config("default_gravatar")
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


def get_email_suggestions(account: str, query: str, limit: int = 5) -> list[str]:
	"""Returns email suggestions based on the given query."""

	if not query:
		return []

	has_permission_for_user(frappe.session.user)
	service = get_email_service(account)
	return service.get_email_suggestions(query, limit)


@frappe.whitelist()
def create_mailbox(
	account: str,
	name: str,
	parent: str | None = None,
	icon: str | None = None,
	color: str | None = None,
	disable_push_notification: bool = False,
	automation_rules: dict | None = None,
) -> str:
	"""Creates a new mailbox and initializes its settings for the given account."""

	mailbox_id = add_mailbox(account, name, None, parent)

	set_mailbox_settings(
		account,
		mailbox_id,
		icon=icon,
		color=color,
		disable_push_notification=disable_push_notification,
	)

	update_sieve_script_for_mailbox(account, name, automation_rules)


@frappe.whitelist()
def update_mailbox(
	account: str,
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
		account,
		id,
		_name=name,
		role=role,
		parent=parent,
		icon=icon,
		color=color,
		disable_push_notification=disable_push_notification,
	)

	update_sieve_script_for_mailbox(account, name, automation_rules, old_name)


@frappe.whitelist()
def delete_mailbox(account: str, id: str, name: str) -> None:
	"""Deletes the mailbox with the given mailbox ID, followed by its settings."""

	delete_mailboxes(account, [id])
	update_sieve_script_for_mailbox(account, name)
	frappe.db.delete("Mailbox Settings", {"account": account, "mailbox_id": id})


@frappe.whitelist()
def get_screened_addresses(account: str) -> list[dict]:
	"""Returns the screened email addresses (each with its `action`) for the given account."""

	has_permission_for_user(parse_account(account)[0])
	return get_screened_email_addresses(account)


@frappe.whitelist()
def screen_email_address(account: str, email: str, action: str = "Reject") -> None:
	"""Screens a single email address for the given account with the given action.

	`action` is Reject, Spam, or Accepted. Used by explicit user actions, so it overrides any
	existing rule for the sender.
	"""

	screen_email_addresses(account, [email], action)


@frappe.whitelist()
def screen_email_addresses(
	account: str, emails: list[str], action: str = "Reject", override: bool = True
) -> None:
	"""Screens multiple email addresses for the given account in a single request.

	`action` is Reject (discard incoming mail silently), Spam (file into Junk), or Accepted (let it
	reach the inbox; used by screening). New addresses are inserted in one batched query via
	`bulk_insert` (no per-document hooks); the sieve script is regenerated once at the end.

	A sender has at most one screening rule (uniqueness is on the address). `override` controls what
	happens when a rule already exists: explicit user actions (default `True`) overwrite it, while
	automated flows like auto-junk pass `override=False` so they never clobber a manual decision.
	"""

	if action not in ("Spam", "Reject", "Accepted"):
		frappe.throw(_("Invalid screening action: {0}").format(action))

	user, account_id = parse_account(account)
	has_permission_for_user(user)

	emails = [email for email in dict.fromkeys(emails) if email]  # de-duplicate, drop empties
	if not emails:
		return

	existing = {
		row.email: row
		for row in frappe.db.get_all(
			"Screened Email Address",
			filters={"account_id": account_id, "email": ["in", emails]},
			fields=["name", "email", "action"],
		)
	}

	docs = []
	changed = False
	for email in emails:
		row = existing.get(email)
		if row:
			if override and row.action != action:
				frappe.db.set_value(
					"Screened Email Address", row.name, "action", action, update_modified=False
				)
				changed = True
			continue

		# bulk_insert bypasses before_insert, so set account_id (the shared key) and user explicitly.
		doc = frappe.get_doc(
			{
				"doctype": "Screened Email Address",
				"account": account,
				"account_id": account_id,
				"email": email,
				"user": user,
				"action": action,
			}
		)
		doc.set_new_name()
		docs.append(doc)

	if docs:
		bulk_insert("Screened Email Address", docs, ignore_duplicates=True)
		changed = True

	if changed:
		update_sieve_script_for_screened_emails(account)


def auto_accept_recipients(account: str, recipients: list) -> None:
	"""When screening is enabled, allowlist the people you email so their replies reach the inbox.

	Non-overriding, so it never un-rejects a sender you deliberately blocked. Failures are logged and
	swallowed — auto-accept must never block sending.
	"""

	from mail.api.sieve import is_screening_enabled

	try:
		if not is_screening_enabled(account):
			return

		emails = list({r.email for r in recipients if getattr(r, "email", None)})
		if emails:
			screen_email_addresses(account, emails, action="Accepted", override=False)
	except Exception:
		log_error(
			_("Screening Auto-Accept Error"),
			_("Failed to auto-accept recipients for account {0}").format(account),
		)


@frappe.whitelist()
def unscreen_email_addresses(account: str, emails: list[str]) -> None:
	"""Removes screening rules by deleting Screened Email Address records and regenerating the sieve.

	Scoped to the shared account_id (not the per-user handle), so a rule added by any user on a
	shared account can be removed. `frappe.db.delete` bypasses the doctype's `after_delete` hook, so
	the screening sieve blocks are rebuilt explicitly here.
	"""

	has_permission_for_user(parse_account(account)[0])

	if not emails:
		return

	account_id = parse_account(account)[1]
	deleted = frappe.db.get_all(
		"Screened Email Address",
		filters={"account_id": account_id, "email": ["in", emails]},
		pluck="name",
	)
	if not deleted:
		return

	frappe.db.delete("Screened Email Address", {"name": ["in", deleted]})
	update_sieve_script_for_screened_emails(account)


# --- Screener (the screening folder view) ---------------------------------------------------------

# Hard cap on how many screening messages a single sweep touches, to bound JMAP work.
SCREENING_FETCH_LIMIT = 500


def _screening_message_ids(account: str, from_email: str | None = None) -> list[str]:
	"""Return ids of Screening-folder messages, optionally only those from a given sender."""

	screening_id = get_mailbox_id_by_name(account, SCREENING_MAILBOX_NAME)
	if not screening_id:
		return []

	conditions = [{"inMailbox": screening_id}]
	if from_email:
		conditions.append({"from": from_email})
	filter = conditions[0] if len(conditions) == 1 else {"operator": "AND", "conditions": conditions}

	return get_email_service(account).query(filter, limit=SCREENING_FETCH_LIMIT).get("ids", [])


@frappe.whitelist()
def get_screening_senders(account: str) -> list[dict]:
	"""Return one row per unique sender in the Screening folder, newest sender first.

	The Screener groups by sender rather than by conversation: each row is the latest mail from that
	sender, with a count of how many of their messages are waiting and how many are unread.
	"""

	has_permission_for_user(parse_account(account)[0])

	screening_id = get_mailbox_id_by_name(account, SCREENING_MAILBOX_NAME)
	if not screening_id:
		return []

	messages, _total = search_messages(
		account,
		{"inMailbox": screening_id},
		position=0,
		limit=SCREENING_FETCH_LIMIT,
		sort=[{"property": "receivedAt", "isAscending": False}],
	)

	senders: dict[str, dict] = {}
	for message in messages:  # newest first
		email = (message.get("from_email") or "").lower()
		if not email:
			continue

		sender = senders.get(email)
		if not sender:
			# The first (newest) message for this sender becomes the summary row.
			senders[email] = {
				"from_email": message["from_email"],
				"from_name": message["from_name"],
				"subject": message["subject"],
				"preview": message["preview"],
				"received_at": message["received_at"],
				"count": 1,
				"unread": 0 if message["seen"] else 1,
			}
		else:
			sender["count"] += 1
			if not message["seen"]:
				sender["unread"] += 1

	return list(senders.values())


@frappe.whitelist()
def get_screening_sender_mails(account: str, from_email: str) -> list[dict]:
	"""Return all Screening-folder messages from a single sender, oldest to newest (with bodies)."""

	has_permission_for_user(parse_account(account)[0])

	ids = _screening_message_ids(account, from_email)
	if not ids:
		return []

	# The JMAP `from` filter is a tokenized text match, so it can also return other senders whose From
	# header shares tokens. Keep only exact-address matches (mirrors how get_screening_senders groups).
	target = from_email.lower()
	mails = [serialize_mail(m) for m in get_messages(account, ids)]
	mails = [m for m in mails if (m.get("from_email") or "").lower() == target]
	mails.sort(key=lambda m: m["received_at"])
	return add_user_images_to_emails(account, mails, is_thread=True)


@frappe.whitelist()
def allow_screening_senders(account: str, from_emails: list[str]) -> None:
	"""Allow senders in: accept them (future mail reaches the inbox) and move their screened mail there."""

	has_permission_for_user(parse_account(account)[0])
	if not from_emails:
		return

	screen_email_addresses(account, from_emails, action="Accepted")

	inbox_id = get_mailbox_id_by_role(account, "inbox", raise_exception=True)
	for from_email in from_emails:
		ids = _screening_message_ids(account, from_email)
		if ids:
			move_mails(account, ids, inbox_id, clear_junk=True)


@frappe.whitelist()
def screen_out_senders(account: str, from_emails: list[str]) -> None:
	"""Screen senders out: mark them Spam (future mail to Junk) and move their screened mail to Junk."""

	has_permission_for_user(parse_account(account)[0])
	if not from_emails:
		return

	screen_email_addresses(account, from_emails, action="Spam")

	for from_email in from_emails:
		ids = _screening_message_ids(account, from_email)
		if ids:
			set_mails_spam_status(account, ids, spam=True)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upload_file():
	from mimetypes import guess_type
	from pathlib import Path

	from frappe import is_whitelisted
	from frappe.core.doctype.file.utils import get_safe_file_name
	from frappe.handler import ALLOWED_MIMETYPES, check_write_permission
	from frappe.utils import cint, get_files_path
	from frappe.utils.image import optimize_image

	if frappe.session.user == "Guest":
		if frappe.get_system_settings("allow_guests_to_upload_files"):
			ignore_permissions = True
		else:
			raise frappe.PermissionError
	else:
		ignore_permissions = False

	files = frappe.request.files
	is_private = frappe.form_dict.is_private
	doctype = frappe.form_dict.doctype
	docname = frappe.form_dict.docname
	fieldname = frappe.form_dict.fieldname
	file_url = frappe.form_dict.file_url
	folder = frappe.form_dict.folder or "Home"
	method = frappe.form_dict.method
	filename = frappe.form_dict.file_name
	optimize = frappe.form_dict.optimize
	content = None

	if library_file := frappe.form_dict.get("library_file_name"):
		frappe.has_permission("File", doc=library_file, throw=True)
		doc = frappe.get_value(
			"File",
			frappe.form_dict.library_file_name,
			["is_private", "file_url", "file_name"],
			as_dict=True,
		)
		is_private = doc.is_private
		file_url = doc.file_url
		filename = doc.file_name

	if not ignore_permissions:
		check_write_permission(doctype, docname)

	if "file" in files:
		file = files["file"]
		filename = file.filename

		if frappe.form_dict.get("chunk_index") is not None:
			current_chunk = int(frappe.form_dict.chunk_index)
			total_chunks = int(frappe.form_dict.total_chunk_count)
			offset = int(frappe.form_dict.chunk_byte_offset)
		else:
			offset = 0
			current_chunk = 0
			total_chunks = 1

		temp_path = Path(get_files_path(".temp-" + get_safe_file_name(filename), is_private=is_private))
		with temp_path.open("ab" if current_chunk > 0 else "wb") as f:
			total_file_size = frappe.form_dict.total_file_size or 0
			f.seek(offset)
			f.write(file.stream.read())
			if not f.tell() >= int(total_file_size) or current_chunk != total_chunks - 1:
				return

		content = temp_path.read_bytes()
		temp_path.unlink()
		content_type = guess_type(filename)[0]
		if optimize and content_type and content_type.startswith("image/"):
			args = {"content": content, "content_type": content_type}
			if frappe.form_dict.max_width:
				args["max_width"] = int(frappe.form_dict.max_width)
			if frappe.form_dict.max_height:
				args["max_height"] = int(frappe.form_dict.max_height)
			content = optimize_image(**args)

	frappe.local.uploaded_file_url = file_url
	frappe.local.uploaded_file = content
	frappe.local.uploaded_filename = filename

	if content is not None and (frappe.session.user == "Guest"):
		filetype = guess_type(filename)[0]
		if filetype not in ALLOWED_MIMETYPES:
			frappe.throw(_("You can only upload JPG, PNG, GIF, PDF, TXT, CSV or Microsoft documents."))

	if method:
		method = frappe.get_attr(method)
		is_whitelisted(method)
		return method()
	else:
		return frappe.get_doc(
			{
				"doctype": "File",
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"attached_to_field": fieldname,
				"folder": folder,
				"file_name": filename,
				"file_url": file_url,
				"is_private": cint(is_private),
				"content": content,
			}
		).save(ignore_permissions=ignore_permissions)
