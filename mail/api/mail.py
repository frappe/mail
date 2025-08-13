import base64
from collections import defaultdict

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.utils import format_datetime, random_string

from mail.jmap import get_mailbox_id_by_role
from mail.mail.doctype.email_message.email_message import EmailMessage, enqueue_fetch_changes
from mail.mail.doctype.email_message.search import EmailSearch
from mail.mail.doctype.mail_queue.mail_queue import MailQueue
from mail.utils import convert_html_to_text
from mail.utils.cache import get_account_for_user
from mail.utils.rate_limiter import dynamic_rate_limit
from mail.utils.user import has_role
from mail.utils.validation import validate_permission_for_account


@frappe.whitelist()
def get_mails_from_mailbox(mailbox: str, limit: int, filter_by: str | None = None) -> list:
	"""Returns mails from the selected mailbox for the current user."""

	account = get_account_for_user(frappe.session.user)
	is_unseen = filter_by == "unread"
	is_has_attachment = filter_by == "has_attachments"
	is_flagged = filter_by == "starred" or mailbox == "starred"
	mailboxes = None if mailbox == "starred" else [mailbox]

	return EmailMessage.get_threads(account, mailboxes, is_unseen, is_flagged, is_has_attachment, 0, limit)


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
def get_mail_thread(thread_id: str) -> list[dict]:
	"""Returns mail thread for the given id."""

	if rows := get_thread_rows(thread_id):
		messages = group_thread_mail_recipients(rows)
		return add_mail_attachments(messages)

	return []


def get_thread_rows(thread_id: str) -> list[dict]:
	"""Returns mail thread rows for the given id."""

	account = get_account_for_user(frappe.session.user)

	EM = frappe.qb.DocType("Email Message")
	EMR = frappe.qb.DocType("Email Message Recipient")
	EMRT = frappe.qb.DocType("Email Message Reply To")

	return (
		frappe.qb.from_(EM)
		.left_join(EMR)
		.on(EM.name == EMR.parent)
		.left_join(EMRT)
		.on(EM.name == EMRT.parent)
		.select(
			EM.name,
			EM.message_id,
			EM._id,
			EM.from_name,
			EM.from_email,
			EM.subject,
			EM.html_body,
			EM.text_body,
			EM.received_at,
			EM.draft,
			EM.seen,
			EM.flagged,
			EM.mailbox_id,
			EMR.type,
			EMR.email,
			EMR.display_name,
			EMRT.email.as_("reply_to"),
		)
		.where((EM.account == account) & (EM.thread_id == thread_id) & (EM.destroyed == 0))
	).run(as_dict=True)


def group_thread_mail_recipients(rows: list[dict]) -> tuple[dict, set]:
	"""Groups mail thread recipients by type."""

	grouped = {}

	for row in rows:
		key = row["name"]
		if key not in grouped:
			grouped[key] = {
				"name": row["name"],
				"message_id": row["message_id"],
				"_id": row["_id"],
				"from_name": row["from_name"],
				"from_email": row["from_email"],
				"subject": row["subject"],
				"html_body": row["html_body"],
				"text_body": row["text_body"],
				"preview": convert_html_to_text(row["html_body"] or row["text_body"] or ""),
				"received_at": row["received_at"],
				"draft": row["draft"],
				"seen": row["seen"],
				"flagged": row["flagged"],
				"mailbox_id": row["mailbox_id"],
				"recipients": defaultdict(list),
				"reply_to": [],
			}

		if row["email"]:
			recipient = {"email": row["email"], "display_name": row["display_name"]}
			grouped[key]["recipients"][row["type"]].append(recipient)

		if row["reply_to"] and row["reply_to"] not in grouped[key]["reply_to"]:
			grouped[key]["reply_to"].append(row["reply_to"])

	return grouped


def add_mail_attachments(messages: list[dict]) -> list[dict]:
	"""Returns thread with attachments."""

	account = get_account_for_user(frappe.session.user)
	attachments = get_mail_attachments(list(messages.keys()))

	for attachment in attachments:
		if attachment.disposition == "attachment":
			if not attachment.filename:
				if attachment.type == "message/delivery-status":
					attachment.filename = "Delivery Report"
				elif attachment.type == "message/rfc822":
					attachment.filename = "Original Message"
			parent = attachment.pop("parent")
			messages[parent].setdefault("attachments", []).append(attachment)

		elif attachment.disposition == "inline":
			blob = EmailMessage.fetch_blob(account, attachment.blob_id)
			base64_content = base64.b64encode(blob).decode("utf-8")
			message = messages[attachment.parent]
			message["html_body"] = convert_img_src_from_cid_to_base64(
				message["html_body"], attachment.cid, attachment.type, base64_content
			)

	return messages.values()


def get_mail_attachments(messages: list[str]) -> list[dict]:
	"""Returns attachments for the given messages."""

	EMP = frappe.qb.DocType("Email Message Part")

	return (
		frappe.qb.from_(EMP)
		.select(
			EMP.parent,
			EMP.filename,
			EMP.blob_id,
			EMP.cid,
			EMP.type,
			EMP.size,
			EMP.file_url,
			EMP.disposition,
		)
		.where(
			(EMP.parenttype == "Email Message")
			& (EMP.parent.isin(messages))
			& ((EMP.parentfield == "attachments") | (EMP.disposition == "inline"))
		)
	).run(as_dict=True)


@frappe.whitelist()
def fetch_attachment(blob_id: str) -> bytes:
	"""Returns the content of an attachment."""

	account = get_account_for_user(frappe.session.user)
	return EmailMessage.fetch_blob(account, blob_id)


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

	doc = frappe.get_doc("Email Message", name)
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
def destroy_mail(name: str) -> None:
	"""Destroys the given mail."""

	account = get_account_for_user(frappe.session.user)
	EmailMessage.destroy_emails(account, [name])


@frappe.whitelist()
def get_mime_message(name: str) -> dict:
	"""Fetches mail mime message and related data."""

	doc = frappe.get_doc("Email Message", name)
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
	mailbox_id = ["!=", get_mailbox_id_by_role(account, "trash")] if mailbox == "starred" else mailbox
	messages = EmailMessage.get_message_ids(account, thread_ids, mailbox_id)
	EmailMessage.mark_emails_as_seen_unseen(account, messages, seen)

	return {"thread_ids": thread_ids, "seen": seen}


@frappe.whitelist()
def set_flagged(names: list[str], flagged: bool) -> dict:
	"""Sets flagged for mails."""

	account = get_account_for_user(frappe.session.user)
	EmailMessage.mark_emails_as_flagged_unflagged(account, names, flagged)

	return {"names": names, "flagged": flagged}


@frappe.whitelist()
def set_mails_mailbox(mail_ids: list[str], mailbox: str) -> None:
	"""Sets mailbox for mails."""

	account = get_account_for_user(frappe.session.user)
	EmailMessage.move_emails_to_mailbox(account, mail_ids, mailbox)


@frappe.whitelist()
def empty_mailbox(mailbox: str) -> None:
	"""Empties selected mailbox for current user."""

	account = get_account_for_user(frappe.session.user)
	messages = frappe.get_all(
		"Email Message",
		{"account": account, "mailbox_id": ["in", mailbox], "destroyed": 0},
		pluck="name",
	)
	EmailMessage.destroy_emails(account, messages)


@frappe.whitelist()
def set_threads_mailbox(thread_ids: list[str], mailbox: str, move_to_mailbox) -> list[str]:
	"""Sets mailbox for threads."""

	account = get_account_for_user(frappe.session.user)
	mailbox_filter = ["!=", get_mailbox_id_by_role(account, "trash")] if mailbox == "starred" else mailbox
	messages = EmailMessage.get_message_ids(account, thread_ids, mailbox_filter)
	EmailMessage.move_emails_to_mailbox(account, messages, move_to_mailbox)
	return thread_ids


@frappe.whitelist()
def delete_threads(thread_ids: list[str], mailbox: str) -> list[str]:
	"""Destroys mails belonging to the given threads."""

	account = get_account_for_user(frappe.session.user)
	messages = EmailMessage.get_message_ids(account, thread_ids, mailbox)
	EmailMessage.destroy_emails(account, messages)
	return thread_ids


@frappe.whitelist()
@dynamic_rate_limit()
def fetch_changes() -> None:
	"""Fetches changes for the current user's account."""

	account = get_account_for_user(frappe.session.user)
	validate_permission_for_account(account)
	enqueue_fetch_changes(account)


@frappe.whitelist()
def search_mails(query) -> dict:
	"""Returns search results for the given query."""

	return EmailSearch().search(query)
