import base64
from collections import defaultdict

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.utils import format_datetime, random_string

from mail.mail.doctype.mail_message.mail_message import (
	delete_messages,
	fetch_blob,
	fetch_thread,
	fetch_threads,
	get_message_ids,
	move_messages,
	set_flagged_status,
	set_seen_status,
)
from mail.mail.doctype.mail_message.search import EmailSearch
from mail.mail.doctype.mail_queue.mail_queue import MailQueue
from mail.utils.cache import get_account_for_user
from mail.utils.user import has_role


@frappe.whitelist()
def get_mailboxes() -> list[dict]:
	"""Returns the user's mailboxes along with no. of unseen mails."""

	user = frappe.session.user
	if not has_role(user, "Mail User") or user == "Administrator":
		return []

	mailboxes = frappe.get_all("Mailbox", filters={"account": get_account_for_user(user)})
	return [
		{
			"id": mailbox["id"],
			"_name": mailbox["_name"],
			"role": mailbox["role"],
			"total_threads": mailbox["total_threads"],
			"unread_threads": mailbox["unread_threads"],
		}
		for mailbox in mailboxes
	]


@frappe.whitelist()
def get_threads(mailbox: str, limit: int, filter_by: str | None = None) -> list:
	"""Returns threads from the selected mailbox for the current user."""

	account = get_account_for_user(frappe.session.user)

	filter = {}
	if mailbox != "starred":
		filter["inMailbox"] = mailbox
	if mailbox == "starred" or filter_by == "starred":
		filter["someInThreadHaveKeyword"] = "$flagged"
	if filter_by == "unread":
		filter["notKeyword"] = "$seen"
	if filter_by == "has_attachments":
		filter["hasAttachment"] = True

	return [serialize_thread(thread) for thread in fetch_threads(account, filter, 0, limit)]


@frappe.whitelist()
def get_thread(thread_id: str) -> list[dict]:
	"""Returns mails for the given thread id."""

	account = get_account_for_user(frappe.session.user)
	return [serialize_mail(mail) for mail in fetch_thread(account, thread_id)]


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
		"flagged",
		"mailboxes",
		"recipients",
		"reply_to",
	]
	return {
		**{field: mail[field] for field in mail_fields},
		"attachments": serialize_attachments(mail.get("attachments", [])),
	}


def serialize_attachments(attachments: list[dict]) -> dict:
	"""Serializes attachment for response."""

	attachment_fields = ["filename", "type", "size", "blob_id"]

	return [
		{field: attachment[field] for field in attachment_fields}
		for attachment in attachments
		if attachment.get("disposition") == "attachment"
	]


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
	save_as_draft: bool = False,
) -> None:
	"""Creates new mail queue."""

	account = get_account_for_user(frappe.session.user)

	doc_attachments = []
	for d in attachments:
		cid = random_string(10)
		doc_attachments.append(
			{
				"file_url": d.get("file_url"),
				"filename": d.get("file_name", ""),
				"disposition": d.get("disposition"),
				"cid": cid,
			}
		)
		if d.get("disposition") == "inline":
			html_body = convert_img_src_from_file_url_to_cid(html_body, d.get("file_url"), cid)

	recipients = [{"type": "To", "email": email} for email in to]
	recipients += [{"type": "Cc", "email": email} for email in cc]
	recipients += [{"type": "Bcc", "email": email} for email in bcc]

	MailQueue._create(
		account=account,
		from_email=from_email,
		subject=subject,
		html_body=html_body,
		in_reply_to=in_reply_to,
		in_reply_to_id=in_reply_to_id,
		attachments=doc_attachments,
		recipients=recipients,
		save_as_draft=save_as_draft,
	)


@frappe.whitelist()
def update_draft_mail(
	name: str,
	from_email: str,
	to: list[str],
	cc: list[str],
	bcc: list[str],
	subject: str | None,
	html_body: str | None,
	attachments: list[dict] = None,
	submit: bool = False,
) -> None:
	"""Creates new mail queue from existing draft message."""

	doc = frappe.get_doc("Mail Message", name)
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

	doc.recipients = []
	for email in to:
		doc.append("recipients", {"type": "To", "email": email})
	for email in cc:
		doc.append("recipients", {"type": "Cc", "email": email})
	for email in bcc:
		doc.append("recipients", {"type": "Bcc", "email": email})

	doc.submit() if submit else doc.save_draft()


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


@frappe.whitelist()
def set_seen(thread_ids: list[str], seen: bool, mailbox: str) -> dict:
	"""Sets seen for mails."""

	account = get_account_for_user(frappe.session.user)
	mailbox_id = None if mailbox == "starred" else mailbox
	messages = get_message_ids(account, thread_ids, mailbox_id)
	set_seen_status(account, messages, seen)

	return {"thread_ids": thread_ids, "seen": seen}


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
def set_threads_mailbox(thread_ids: list[str], mailbox: str, move_to_mailbox) -> list[str]:
	"""Sets mailbox for threads."""

	account = get_account_for_user(frappe.session.user)
	mailbox_id = None if mailbox == "starred" else mailbox
	messages = get_message_ids(account, thread_ids, mailbox_id)
	move_messages(account, messages, move_to_mailbox)

	return thread_ids


@frappe.whitelist()
def delete_threads(thread_ids: list[str], mailbox: str) -> list[str]:
	"""Deletes mails belonging to the given threads."""

	account = get_account_for_user(frappe.session.user)
	messages = get_message_ids(account, thread_ids, mailbox)
	delete_messages(account, messages)

	return thread_ids


@frappe.whitelist()
def search_mails(query) -> dict:
	"""Returns search results for the given query."""

	return EmailSearch().search(query)
