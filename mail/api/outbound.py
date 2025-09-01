import os
from email.utils import parseaddr

import frappe
from frappe import _
from frappe.utils.file_manager import save_file
from werkzeug.datastructures.file_storage import FileStorage
from werkzeug.utils import secure_filename

from mail.mail.doctype.mail_queue.mail_queue import MailQueue
from mail.utils import get_messages_directory
from mail.utils.cache import get_account_for_user
from mail.utils.rate_limiter import dynamic_rate_limit
from mail.utils.user import has_role


@frappe.whitelist(methods=["POST"])
@dynamic_rate_limit()
def upload_attachment() -> dict:
	"""Upload an attachment to the Frappe Mail folder."""

	try:
		user = frappe.session.user
		if not has_role(user, "Mail User"):
			frappe.throw(_("User {0} is not allowed to upload attachments.").format(frappe.bold(user)))

		if file := frappe.request.files.get("file"):
			if not isinstance(file, FileStorage):
				frappe.throw(_("Invalid file type."))

			kwargs = {
				"dt": None,
				"dn": None,
				"is_private": 1,
				"fname": file.filename,
				"folder": "Home/Frappe Mail",
				"content": file.stream.read(),
			}
			doc = save_file(**kwargs)

			return {
				"file_name": doc.file_name,
				"file_type": doc.file_type,
				"file_size": doc.file_size,
				"file_url": doc.file_url,
			}
	except Exception as e:
		frappe.log_error(title=_("Error uploading attachment"), message=frappe.get_traceback())
		frappe.throw(str(e))

	frappe.throw(_("No file found in the request."), frappe.MandatoryError)


@frappe.whitelist(methods=["POST"])
@dynamic_rate_limit()
def send(
	from_: str,
	subject: str,
	to: str | list[str] | None = None,
	cc: str | list[str] | None = None,
	bcc: str | list[str] | None = None,
	html: str | None = None,
	text: str | None = None,
	reply_to: str | list[str] | None = None,
	in_reply_to: str | None = None,
	headers: dict | None = None,
	attachments: list[dict] | None = None,
	is_newsletter: bool = False,
	save_as_draft: bool = False,
) -> str:
	"""Send Mail."""

	from_name, from_email = parseaddr(from_)
	doc = MailQueue._create(
		account=get_account(),
		from_name=from_name,
		from_email=from_email,
		subject=subject,
		reply_to=format_reply_to(reply_to),
		headers=headers,
		recipients=format_recipients(to, cc, bcc),
		attachments=attachments,
		html_body=html,
		text_body=text,
		via_api=True,
		newsletter=is_newsletter,
		in_reply_to=in_reply_to,
		save_as_draft=save_as_draft,
		destroy_after_submission=False,
		delivery_mode="Batch" if is_newsletter else "Enqueue",
	)

	return doc.name


@frappe.whitelist(methods=["POST"])
@dynamic_rate_limit()
def send_raw(
	from_: str,
	to: str | list[str],
	raw_message: str | None = None,
	is_newsletter: bool = False,
) -> str:
	"""Send raw email. Supports both single-shot and chunked upload."""

	chunk_index = frappe.form_dict.get("chunk_index")
	total_chunks = frappe.form_dict.get("total_chunk_count")
	upload_session = frappe.form_dict.get("uuid")

	if chunk_index is not None and total_chunks is not None and upload_session:
		return _handle_chunked_upload(
			from_, to, is_newsletter, int(chunk_index), int(total_chunks), str(upload_session)
		)

	raw_message = raw_message or get_message_from_files()
	if not raw_message:
		frappe.throw(_("The raw message is required."), frappe.MandatoryError)

	return _enqueue_mail(from_, to, raw_message, is_newsletter)


def get_account() -> str:
	"""Returns the mail account for the current user."""

	user = frappe.session.user

	if account := get_account_for_user(user):
		return account

	frappe.throw(_("No Mail Account found for the user {0}.").format(frappe.bold(user)))


def get_message_from_files() -> str | None:
	"""Extracts message from uploaded file in single upload mode."""

	files = frappe._dict(frappe.request.files)

	if files and files.get("raw_message"):
		return files["raw_message"].read().decode("utf-8")


def format_recipients(
	to: str | list[str] | None = None, cc: str | list[str] | None = None, bcc: str | list[str] | None = None
) -> list[dict]:
	"""Formats the recipients for the mail queue."""

	recipients = []

	if to:
		recipients.extend(_normalize_recipients(to, "To"))
	if cc:
		recipients.extend(_normalize_recipients(cc, "Cc"))
	if bcc:
		recipients.extend(_normalize_recipients(bcc, "Bcc"))

	return recipients


def format_reply_to(reply_to: str | list[str] | None) -> list[dict]:
	"""Formats the reply_to field for the mail queue."""

	if not reply_to:
		return []
	return _normalize_recipients(reply_to)


def _handle_chunked_upload(
	from_: str, to: str | list[str], is_newsletter: bool, chunk_index: int, total_chunks: int, session_id: str
) -> str:
	"""Handle chunked uploads for large emails."""

	file = frappe.request.files.get("raw_message")
	if not file:
		frappe.throw(_("No file part named 'raw_message' found."))

	upload_dir = get_messages_directory()
	filename = secure_filename(f"{session_id}.eml")
	temp_path = os.path.join(upload_dir, filename)
	offset = int(frappe.form_dict.get("chunk_byte_offset", 0))

	with open(temp_path, "ab") as f:
		f.seek(offset)
		f.write(file.stream.read())

	if chunk_index < total_chunks - 1:
		return f"Chunk {chunk_index + 1} of {total_chunks} received."

	with open(temp_path, "rb") as f:
		raw_message = f.read().decode("utf-8")

	os.remove(temp_path)

	return _enqueue_mail(from_, to, raw_message, is_newsletter)


def _normalize_recipients(
	recipients: str | list[str] | None, recipient_type: str | None = None
) -> list[dict]:
	"""Helper to normalize recipients into a list of dicts."""

	if isinstance(recipients, str):
		recipients = [recipients]

	result = []
	for recipient in recipients:
		name, email = parseaddr(recipient)
		recipient_dict = {"name": name, "email": email}
		if recipient_type:
			recipient_dict["type"] = recipient_type
		result.append(recipient_dict)

	return result


def _enqueue_mail(from_: str, to: str | list[str], raw_message: str, is_newsletter: bool = False) -> str:
	"""Enqueue mail in MailQueue."""

	from_name, from_email = parseaddr(from_)
	if not raw_message:
		frappe.throw(_("The raw message is required."), frappe.MandatoryError)

	doc = MailQueue._create(
		account=get_account(),
		from_name=from_name,
		from_email=from_email,
		recipients=format_recipients(to),
		via_api=True,
		newsletter=is_newsletter,
		raw_message=raw_message,
		delivery_mode="Batch" if is_newsletter else "Enqueue",
	)

	return doc.name
