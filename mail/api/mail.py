from datetime import datetime, timezone

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.utils import format_datetime, get_url, random_string

from mail.jmap import get_mailbox_id_by_role
from mail.mail.doctype.mail_message.mail_message import (
	delete_messages,
	empty_mailbox,
	fetch_blob,
	fetch_blobs,
	fetch_thread,
	fetch_threads,
	get_message_ids,
	move_messages,
	search_messages,
	set_flagged_status,
	set_seen_status,
	set_spam_status,
)
from mail.mail.doctype.mail_queue.mail_queue import MailQueue
from mail.utils import convert_html_to_text
from mail.utils.cache import get_account_for_user
from mail.utils.user import has_role


@frappe.whitelist()
def get_mailboxes() -> list[dict]:
	"""Serializes and returns the user's mailboxes."""

	user = frappe.session.user
	if not has_role(user, "Mail User") or user == "Administrator":
		return []

	fields = ["id", "_name", "role", "total_threads", "unread_threads"]
	mailboxes = get_account_mailboxes(get_account_for_user(user))
	return [{field: mailbox[field] for field in fields} for mailbox in mailboxes]


def get_account_mailboxes(account) -> list[dict]:
	"""Returns the account's mailboxes."""

	return frappe.get_all("Mailbox", filters={"account": account})


@frappe.whitelist()
def get_threads(mailbox: str, limit: int, filter_by: str | None = None) -> list:
	"""Returns threads from the selected mailbox for the current user."""

	account = get_account_for_user(frappe.session.user)

	if mailbox == "starred":
		conditions = [
			{
				"inMailboxOtherThan": [
					get_mailbox_id_by_role(account, "junk", raise_exception=True),
					get_mailbox_id_by_role(account, "trash", raise_exception=True),
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

	return [serialize_thread(thread) for thread in fetch_threads(account, filter, 0, limit)]


@frappe.whitelist()
def get_thread(thread_id: str) -> list[dict]:
	"""Returns mails for the given thread id."""

	account = get_account_for_user(frappe.session.user)
	return [serialize_mail(mail) for mail in fetch_thread(account, thread_id)]


@frappe.whitelist()
def get_attachment(blob_id: str, filename: str | None = None) -> None:
	"""Fetches and returns the attachment."""

	if not blob_id:
		frappe.throw(_("Blob ID is required"))

	account = get_account_for_user(frappe.session.user)
	if not account:
		frappe.throw(_("Mail Account not found for user {0}").format(frappe.session.user))

	content = fetch_blob(account, blob_id, filename)

	frappe.local.response.filename = filename or blob_id
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"


def serialize_thread(thread: dict) -> dict:
	"""Serializes thread for response."""

	thread_fields = [
		"name",
		"account",
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
		"_id",
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

	attachments = serialize_attachments(mail.get("attachments", []))
	if attachments:
		blobs = []
		for attachment in attachments:
			if attachment["disposition"] == "inline" and attachment["cid"] and attachment["blob_id"]:
				blobs.append((attachment["blob_id"], attachment["filename"]))
				url = get_attachment_url(attachment["blob_id"], attachment["filename"])
				mail["html_body"] = convert_img_src_from_cid_to_url(mail["html_body"], attachment["cid"], url)

		if blobs:
			fetch_blobs(mail["account"], blobs)

	return {
		**{field: mail[field] for field in mail_fields},
		"attachments": attachments,
	}


def serialize_attachments(attachments: list[dict]) -> list[dict]:
	"""Serializes attachment for response."""

	attachment_fields = ["filename", "type", "size", "blob_id", "disposition", "cid"]

	return [
		{field: attachment[field] for field in attachment_fields}
		for attachment in attachments
		if attachment.get("filename")
	]


def get_attachment_url(blob_id: str, filename: str | None = None) -> str:
	"""Returns the URL for the attachment."""

	return get_url(f"/api/method/mail.api.mail.get_attachment?blob_id={blob_id}&filename={filename or ''}")


@frappe.whitelist()
def fetch_attachment(blob_id: str) -> bytes:
	"""Returns the content of an attachment."""

	account = get_account_for_user(frappe.session.user)
	return fetch_blob(account, blob_id)


@frappe.whitelist()
def get_mail_contacts(txt=None) -> list:
	"""Returns the mail contacts for the current user."""

	filters = {"user": frappe.session.user}
	if txt:
		filters["email"] = ["like", f"%{txt}%"]

	contacts = frappe.get_all("Mail Contact", filters=filters, fields=["email"], page_length=10)

	for contact in contacts:
		details = frappe.db.get_value(
			"User", {"email": contact.email}, ["user_image", "full_name", "email"], as_dict=1
		)
		if details:
			contact.update(details)

	return contacts


@frappe.whitelist()
def create_mail(
	from_email: str,
	to: list[str],
	cc: list[str],
	bcc: list[str],
	subject: str | None,
	html_body: str | None,
	attachments: list[dict] = None,
	in_reply_to: str | None = None,
	in_reply_to_id: str | None = None,
	forwarded_from_id: str | None = None,
	save_as_draft: bool = False,
) -> dict:
	"""Creates new mail queue."""

	account = get_account_for_user(frappe.session.user)

	doc_attachments = []
	for d in attachments:
		cid = random_string(10)
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
		if d.get("disposition") == "inline":
			html_body = convert_img_src_from_file_url_to_cid(html_body, d.get("file_url"), cid)

	recipients = [{"type": "To", "email": email} for email in to]
	recipients += [{"type": "Cc", "email": email} for email in cc]
	recipients += [{"type": "Bcc", "email": email} for email in bcc]

	doc = MailQueue._create(
		account=account,
		from_email=from_email,
		subject=subject,
		html_body=html_body,
		in_reply_to=in_reply_to,
		in_reply_to_id=in_reply_to_id,
		forwarded_from_id=forwarded_from_id,
		attachments=doc_attachments,
		recipients=recipients,
		save_as_draft=save_as_draft,
	)

	return {"_id": doc._id, "status": doc.status, "error": doc.error_message}


@frappe.whitelist()
def update_draft_mail(
	_id: str,
	from_email: str,
	to: list[str],
	cc: list[str],
	bcc: list[str],
	subject: str | None,
	html_body: str | None,
	attachments: list[dict] = None,
	submit: bool = False,
) -> dict:
	"""Creates new mail queue from existing draft message."""

	account = get_account_for_user(frappe.session.user)

	doc = frappe.get_doc("Mail Message", f"{account}|{_id}")
	doc.check_permission(permtype="write")

	doc.from_email = from_email
	doc.subject = subject

	doc.attachments = []
	for d in attachments or []:
		cid = d.get("cid", random_string(10))
		doc.append(
			"attachments",
			{
				"blob_id": d.get("blob_id", ""),
				"file_url": d.get("file_url", ""),
				"type": d.get("type", ""),
				"size": d.get("size", ""),
				"filename": d.get("filename", ""),
				"disposition": d.get("disposition"),
				"cid": cid,
			},
		)
		if d.get("disposition") == "inline":
			html_body = convert_img_src_from_file_url_to_cid(html_body, d.get("file_url"), cid)

	doc.html_body = convert_img_src_from_base64_to_cid(html_body)
	doc.text_body = convert_html_to_text(doc.html_body)

	doc.recipients = []
	for email in to:
		doc.append("recipients", {"type": "To", "email": email})
	for email in cc:
		doc.append("recipients", {"type": "Cc", "email": email})
	for email in bcc:
		doc.append("recipients", {"type": "Bcc", "email": email})

	new_doc = doc.submit() if submit else doc.save_draft()

	return {"_id": new_doc._id, "status": new_doc.status, "error": new_doc.error_message}


def convert_img_src_from_file_url_to_cid(html_body: str, file_url: str, cid: str) -> str:
	"""Converts url-based images in HTML body to CID references."""

	soup = BeautifulSoup(html_body, "html.parser")
	for img in soup.find_all("img", src=file_url):
		img["src"] = f"cid:{cid}"

	return str(soup)


def convert_img_src_from_base64_to_cid(html_body: str) -> str:
	"""Converts base64 images in HTML body to CID references."""

	soup = BeautifulSoup(html_body, "html.parser")
	for img in soup.find_all("img", attrs={"data-cid": True}):
		img["src"] = f"cid:{img['data-cid']}"

	return str(soup)


def convert_img_src_from_cid_to_base64(html_body: str, cid: str, type: str, base64_content) -> str:
	"""Converts CID-based images in HTML body to base 64."""

	soup = BeautifulSoup(html_body, "html.parser")
	for img in soup.find_all("img", src=f"cid:{cid}"):
		img["data-cid"] = cid
		img["src"] = f"data:{type};base64,{base64_content}"

	return str(soup)


def convert_img_src_from_cid_to_url(html_body: str, cid: str, url: str) -> str:
	"""Converts CID-based images in HTML body to URL."""

	soup = BeautifulSoup(html_body, "html.parser")
	for img in soup.find_all("img", src=f"cid:{cid}"):
		img["data-cid"] = cid
		img["src"] = url

	return str(soup)


@frappe.whitelist()
def delete_mail(_id: str) -> None:
	"""Deletes the given mail."""

	account = get_account_for_user(frappe.session.user)
	delete_messages(account, [_id])


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


def get_account_and_filtered_message_ids(
	thread_ids: list[str], mailbox: str | None = None
) -> tuple[str, list[str]]:
	"""Gets account and filtered message IDs for the given mailbox."""

	account = get_account_for_user(frappe.session.user)
	if mailbox == "starred":
		mailbox = [d["id"] for d in get_account_mailboxes(account) if d["role"] != "trash"]
	elif mailbox == "search":
		mailbox = None
	messages = get_message_ids(account, thread_ids, mailbox)

	return account, messages


@frappe.whitelist()
def set_seen(thread_ids: dict[bool, list[str]], mailbox: str) -> dict:
	"""Sets seen for threads."""

	for is_seen, ids in thread_ids.items():
		account, messages = get_account_and_filtered_message_ids(ids, mailbox)
		set_seen_status(account, messages, is_seen)

	return thread_ids


@frappe.whitelist()
def set_flagged(_ids: list[str], flagged: bool) -> dict:
	"""Sets flagged for mails."""

	account = get_account_for_user(frappe.session.user)
	set_flagged_status(account, _ids, flagged)

	return {"_ids": _ids, "flagged": flagged}


@frappe.whitelist()
def move_mails(_ids: list[str], mailbox: str) -> None:
	"""Sets mailbox for mails."""

	account = get_account_for_user(frappe.session.user)
	move_messages(account, _ids, mailbox)


@frappe.whitelist()
def set_threads_mailbox(thread_ids: dict[str, list[str]]) -> dict:
	"""Sets mailbox for threads."""

	for move_to_mailbox, ids in thread_ids.items():
		account, messages = get_account_and_filtered_message_ids(ids)
		move_messages(account, messages, move_to_mailbox)

	return thread_ids


@frappe.whitelist()
def set_mails_spam_status(_ids: list[str], spam: bool) -> list[str]:
	"""Sets spam status of the given mails."""

	account = get_account_for_user(frappe.session.user)
	set_spam_status(account, _ids, spam)

	return _ids


@frappe.whitelist()
def set_threads_spam_status(thread_ids: dict[bool, list[str]]) -> dict:
	"""Sets spam status for the mails belonging to the given threads."""

	for is_spam, ids in thread_ids.items():
		account, messages = get_account_and_filtered_message_ids(ids)
		set_spam_status(account, messages, is_spam)

	return thread_ids


@frappe.whitelist()
def delete_threads(thread_ids: list[str], mailbox: str) -> list[str]:
	"""Deletes mails belonging to the given threads."""

	account, messages = get_account_and_filtered_message_ids(thread_ids, mailbox)
	delete_messages(account, messages)

	return thread_ids


@frappe.whitelist()
def empty_user_mailbox(mailbox: str) -> None:
	"""Empties the given mailbox."""

	account = get_account_for_user(frappe.session.user)
	empty_mailbox(account, mailbox)


@frappe.whitelist()
def search_mails(filter: dict | None = None, limit: int = 5) -> tuple[list[dict], int]:
	"""Returns search results for the given query."""

	if not filter:
		return ([], 0)

	normalized_filter = normalize_search_filter(filter)
	account = get_account_for_user(frappe.session.user)
	return search_messages(account, normalized_filter, limit=limit)


def normalize_search_filter(filter: dict) -> dict:
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
	return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).isoformat()
