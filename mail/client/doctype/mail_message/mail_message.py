# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import re
from email.utils import formataddr
from functools import cached_property
from typing import Literal
from urllib.parse import quote
from uuid import uuid7

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.model.document import Document
from frappe.push_notification import PushNotification
from frappe.utils import (
	add_to_date,
	cint,
	escape_html,
	get_datetime,
	now,
	random_string,
	time_diff_in_seconds,
)

from mail.client.doctype.mail_queue.mail_queue import MailQueue
from mail.jmap import get_email_service, get_jmap_connection, get_thread_service, parse_account
from mail.jmap.services.mail.email import EmailService
from mail.jmap.services.mail.mailbox import MailboxService
from mail.utils import (
	enqueue_job,
	get_mail_config,
	get_push_logger,
	parse_filters,
	user_context,
)
from mail.utils.dt import convert_to_utc, parse_iso_datetime, to_iso8601_z
from mail.utils.email_parser import EmailParser
from mail.utils.lock import acquire_lock, release_lock
from mail.utils.user import get_account_emails, get_sync_state, update_sync_state
from mail.utils.validation import has_permission_for_user


class MailMessage(Document):
	@property
	def to(self) -> list[dict[str, str | None]]:
		"""Returns the recipients in the To field."""

		return self._get_recipients("To")

	@property
	def cc(self) -> list[dict[str, str | None]]:
		"""Returns the recipients in the Cc field."""

		return self._get_recipients("Cc")

	@property
	def bcc(self) -> list[dict[str, str | None]]:
		"""Returns the recipients in the Bcc field."""

		return self._get_recipients("Bcc")

	@property
	def spf_pass(self) -> int:
		"""Returns SPF pass status."""

		return cint(self.authentication_results.get("spf_pass"))

	@property
	def dkim_pass(self) -> int:
		"""Returns DKIM pass status."""

		return cint(self.authentication_results.get("dkim_pass"))

	@property
	def dmarc_pass(self) -> int:
		"""Returns DMARC pass status."""

		return cint(self.authentication_results.get("dmarc_pass"))

	@property
	def spf_description(self) -> str | None:
		"""Returns SPF description."""

		return self.authentication_results.get("spf_description")

	@property
	def dkim_description(self) -> str | None:
		"""Returns DKIM description."""

		return self.authentication_results.get("dkim_description")

	@property
	def dmarc_description(self) -> str | None:
		"""Returns DMARC description."""

		return self.authentication_results.get("dmarc_description")

	@cached_property
	def from_ip(self) -> str | None:
		"""Returns the IP address of the sender."""

		if not self.parsed_message:
			return

		if header := self.parsed_message.get_header("Received"):
			ip_pattern = re.compile(r"\[(?P<ip>[\d\.]+|[a-fA-F0-9:]+)")
			ip_match = ip_pattern.search(header)
			return ip_match.group("ip") if ip_match else None

	@cached_property
	def from_host(self) -> str | None:
		"""Returns the host of the sender."""

		if not self.parsed_message:
			return

		if header := self.parsed_message.get_header("Received"):
			host_pattern = re.compile(r"from\s+(?P<host>[^\s]+)")
			host_match = host_pattern.search(header)
			return host_match.group("host") if host_match else None

	@cached_property
	def spam_score(self) -> float:
		"""Returns the spam score of the email."""

		if not self.parsed_message:
			return 0.0

		if header := self.parsed_message.get_header("X-Spam-Status"):
			score_pattern = re.compile(r"score=(-?\d+\.?\d*)")
			score_match = score_pattern.search(header)
			return float(score_match.group(1)) if score_match else 0.0

	@property
	def message(self) -> str | None:
		"""Returns the message content if available."""

		if content := _get_blob_from_cache(self.account, self.blob_id):
			return content.decode("utf-8")

	@cached_property
	def parsed_message(self) -> EmailParser | None:
		"""Returns the parsed Mail Message."""

		if self.message:
			return EmailParser(self.message)

	@cached_property
	def authentication_results(self) -> dict[str, int | str]:
		"""Returns the authentication results of the email."""

		if not self.parsed_message:
			return {}

		return self.parsed_message.get_authentication_results()

	@cached_property
	def email_type(self) -> str:
		"""Returns the type of email (Sent or Received)."""

		email_type = "Received"
		account_addresses = get_account_emails(self.account)

		if self.from_email in account_addresses or (
			hasattr(self, "sender_email") and self.sender_email in account_addresses
		):
			email_type = "Sent"

		return email_type

	def autoname(self) -> None:
		self.name = f"{self.account}|{uuid7()!s}"

	def db_insert(self, *args, **kwargs) -> None:
		raise NotImplementedError

	def load_from_db(self) -> "MailMessage":
		account, id = self.name.split("|")
		if messages := get_messages(account, ids=[id]):
			return super(Document, self).__init__(messages[0])

		frappe.throw(_("Message not found or you do not have permission to view it."))

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		account, id = self.name.split("|")
		delete_messages(account, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)

		id = filters.get("id")
		account = filters.get("account")

		if not account:
			frappe.msgprint(_("Please select an account to view messages."), alert=True)
			return []

		if not has_permission_for_user(parse_account(account)[0], raise_exception=False):
			frappe.msgprint(_("You do not have permission to view messages for this account."), alert=True)
			return []

		if id:
			messages = get_messages(account, ids=[id])
			total = len(messages)
		else:
			filter = {
				prop: value
				for field, prop in {
					"in_mailbox": "inMailbox",
					"_from": "from",
					"_to": "to",
					"_cc": "cc",
					"_bcc": "bcc",
					"text": "text",
					"body": "body",
					"subject": "subject",
					"min_size": "minSize",
					"max_size": "maxSize",
					"has_keyword": "hasKeyword",
					"not_keyword": "notKeyword",
				}.items()
				if (value := filters.get(field))
			}

			if filters.get("has_attachment"):
				filter["hasAttachment"] = True

			for field in ("before", "after"):
				if value := filters.get(field):
					filter[field] = to_iso8601_z(convert_to_utc(value))

			limit = cint(kwargs.get("start")) + page_length
			messages, total = fetch_messages(account, filter, limit=limit)

		frappe.cache.set_value(_get_total_cache_key(account), total, expires_in_sec=600)

		fields_to_remove = [
			"mailboxes",
			"reply_to",
			"recipients",
			"preview",
			"html_body",
			"text_body",
			"attachments",
			"keywords",
			"_html_body",
			"_text_body",
		]
		for message in messages:
			for field in fields_to_remove:
				message.pop(field, None)

		if not messages:
			frappe.msgprint(_("No messages found."), alert=True)

		return messages

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		account = filters.get("account")

		if account:
			if has_permission_for_user(parse_account(account)[0], raise_exception=False):
				return cint(frappe.cache.get_value(_get_total_cache_key(account)))

		return 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	def validate_draft(self) -> None:
		"""Raise an exception if the message is a draft."""

		if self.draft:
			frappe.throw(
				_("Mail Message {0} is a draft. Please send it before performing this action.").format(
					frappe.bold(self.name)
				)
			)

	@frappe.whitelist()
	def save_draft(self) -> "MailQueue":
		"""Save the Mail Message as a draft."""

		return self._update_or_submit_draft(save_as_draft=True)

	@frappe.whitelist()
	def submit(self) -> "MailQueue":
		"""Submit the draft Mail Message."""

		return self._update_or_submit_draft(save_as_draft=False)

	@frappe.whitelist()
	def move_to_mailbox(self, mailbox_id: str) -> None:
		"""Move the Mail Message to a specified mailbox."""

		self.validate_draft()
		move_messages(self.account, [self.id], mailbox_id)
		self.reload()

	@frappe.whitelist()
	def set_seen(self, seen: bool) -> None:
		"""Set the Mail Message as seen or unseen."""

		set_seen_status(self.account, [self.id], seen)
		self.reload()

	@frappe.whitelist()
	def set_flagged(self, flagged: bool) -> None:
		"""Set the Mail Message as flagged or unflagged."""

		set_flagged_status(self.account, [self.id], flagged)
		self.reload()

	@frappe.whitelist()
	def reply(self) -> "MailQueue":
		"""Reply to the Mail Message."""

		recipients = []

		if self.email_type == "Sent":
			# To = original To
			for rcpt in self.recipients:
				if rcpt.type == "To":
					recipients.append(
						{"type": rcpt.type, "display_name": rcpt.display_name, "email": rcpt.email}
					)

		elif self.email_type == "Received":
			# To = Reply-To if present, else From
			if self.reply_to:
				recipients.extend(
					{"type": "To", "display_name": rt.display_name, "email": rt.email} for rt in self.reply_to
				)
			else:
				recipients.append({"type": "To", "display_name": self.from_name, "email": self.from_email})

		return self._reply(recipients)

	@frappe.whitelist()
	def reply_all(self) -> "MailQueue":
		"""Reply to all recipients of the Mail Message."""

		recipients = []

		if self.email_type == "Sent":
			# To = original To
			# Cc = original Cc
			for rcpt in self.recipients:
				if rcpt.type in ["To", "Cc"]:
					recipients.append(
						{"type": rcpt.type, "display_name": rcpt.display_name, "email": rcpt.email}
					)

		elif self.email_type == "Received":
			# To = Reply-To if present, else From
			if self.reply_to:
				recipients.extend(
					{"type": "To", "display_name": rt.display_name, "email": rt.email} for rt in self.reply_to
				)
			else:
				recipients.append({"type": "To", "display_name": self.from_name, "email": self.from_email})

			# Cc = (original To + original Cc) minus account addresses
			account_addresses = get_account_emails(self.account)
			for rcpt in self.recipients:
				if rcpt.type in ["To", "Cc"] and rcpt.email not in account_addresses:
					recipients.append({"type": "Cc", "display_name": rcpt.display_name, "email": rcpt.email})

		return self._reply(recipients)

	@frappe.whitelist()
	def forward(self) -> "MailQueue":
		"""Forward the Mail Message."""

		self.validate_draft()

		formatted_sent_at = get_datetime(self.sent_at).strftime("%a, %B %-d, %Y at %-I:%M %p")
		forward_html_body = (
			"<p>---------- Forwarded message ---------</p>"
			'<table border="0" cellpadding="0" cellspacing="10">'
			f"<tr><td><b>From:</b></td><td>{escape_html(formataddr([self.from_name, self.from_email]))}</td></tr>"
			f"<tr><td><b>Date:</b></td><td>{formatted_sent_at}</td></tr>"
			f"<tr><td><b>Subject:</b></td><td>{self.subject}</td></tr>"
		)
		forward_text_body = (
			"---------- Forwarded message ---------\n"
			f"From: {formataddr([self.from_name, self.from_email])}\n"
			f"Date: {formatted_sent_at}\n"
			f"Subject: {self.subject}\n"
		)

		if to := ", ".join(
			[formataddr([rcpt["name"], rcpt["email"]]) for rcpt in self._get_recipients("To")]
		):
			forward_html_body += f"<tr><td><b>To:</b></td><td>{escape_html(to)}</td></tr>"
			forward_text_body += f"To: {to}\n"
		if cc := ", ".join(
			[formataddr([rcpt["name"], rcpt["email"]]) for rcpt in self._get_recipients("Cc")]
		):
			forward_html_body += f"<tr><td><b>Cc:</b></td><td>{escape_html(cc)}</td></tr>"
			forward_text_body += f"Cc: {cc}\n"

		original_html_body = self.html_body or ""
		original_text_body = self.text_body or ""

		quoted_html_body = f'<blockquote style="border-left:2px solid #ccc; margin-left:0; padding-left:1em;">{original_html_body}</blockquote>'
		quoted_text_body = "\n> ".join(original_text_body.strip().splitlines())

		forward_html_body += f"</table><br/> {quoted_html_body}"
		forward_html_body = BeautifulSoup(forward_html_body, "html.parser").prettify()
		forward_text_body += f"\n\n> {quoted_text_body}"

		attachments = [
			{
				"file_url": a.file_url,
				"blob_id": a.blob_id,
				"type": a.type,
				"size": a.size,
				"filename": a.filename,
				"disposition": a.disposition,
				"cid": a.cid,
			}
			for a in self.attachments
		]

		for body_part in self._html_body + self._text_body:
			if body_part.disposition == "inline":
				attachments.append(
					{
						"blob_id": body_part.blob_id,
						"type": body_part.type,
						"size": body_part.size,
						"filename": body_part.filename,
						"disposition": body_part.disposition,
						"cid": body_part.cid,
					}
				)

		return MailQueue._create(
			account=self.account,
			subject=f"Fwd: {self.subject}" if not self.subject.lower().startswith("fwd:") else self.subject,
			html_body=forward_html_body,
			text_body=forward_text_body,
			attachments=attachments,
			forwarded_from_id=self.id,
			do_not_save=True,
		)

	@frappe.whitelist()
	def get_mime_message(self) -> str:
		"""Returns the MIME message content."""

		if not self.blob_id:
			frappe.throw(_("Mail Message does not have a blob ID."))

		self.clear_cached_properties()
		return fetch_blob(self.account, self.blob_id).decode("utf-8")

	@frappe.whitelist()
	def load_attachments(self, include_inline: bool = True, include_regular: bool = True) -> None:
		"""Load attachments to cache."""

		if not any([self.attachments, self._html_body, self._text_body]):
			return

		blobs = []
		for attachment in self.attachments:
			if (include_inline and attachment.disposition == "inline") or (
				include_regular and attachment.disposition == "attachment"
			):
				blobs.append((attachment.blob_id, attachment.filename))

		if include_inline:
			for body_part in self._html_body + self._text_body:
				if body_part.disposition == "inline":
					blobs.append((body_part.blob_id, body_part.filename))

		fetch_blobs(self.account, blobs)

	def clear_cached_properties(self) -> None:
		"""Clear cached properties to avoid stale data."""

		for property in [
			"from_ip",
			"from_host",
			"spam_score",
			"parsed_message",
			"authentication_results",
		]:
			self.__dict__.pop(property, None)

	def _update_or_submit_draft(self, save_as_draft: bool = True) -> "MailQueue":
		"""Update or submit the draft Mail Message."""

		if not self.draft:
			frappe.throw(_("Mail Message {0} is not a draft.").format(frappe.bold(self.name)))

		recipients = [
			{"type": rcpt.type, "display_name": rcpt.display_name, "email": rcpt.email}
			for rcpt in self.recipients
		]
		reply_to = [{"display_name": rt.display_name, "email": rt.email} for rt in self.reply_to]
		attachments = [
			{
				"file_url": a.file_url,
				"blob_id": a.blob_id,
				"type": a.type,
				"size": a.size,
				"filename": a.filename,
				"disposition": a.disposition,
				"cid": a.cid,
			}
			for a in self.attachments
		]

		return MailQueue._create(
			account=self.account,
			from_name=self.from_name,
			from_email=self.from_email,
			subject=self.subject,
			reply_to=reply_to,
			recipients=recipients,
			attachments=attachments,
			html_body=self.html_body,
			text_body=self.text_body,
			message_id=self.message_id,
			id=self.id,
			in_reply_to=self.in_reply_to,
			save_as_draft=save_as_draft,
			delivery_mode="Immediate",
		)

	def _reply(self, recipients: list[dict]) -> "MailQueue":
		"""Returns a unsaved MailQueue object for replying to the Mail Message."""

		self.validate_draft()

		subject = None
		if self.subject:
			subject = f"Re: {self.subject}" if not self.subject.lower().startswith("re:") else self.subject

		return MailQueue._create(
			account=self.account,
			subject=subject,
			recipients=recipients,
			in_reply_to=self.message_id,
			in_reply_to_id=self.id,
			do_not_save=True,
		)

	def _get_recipients(self, type: Literal["To", "Cc", "Bcc"] | None = None) -> list[dict[str, str | None]]:
		"""Returns the recipients."""

		recipients = []
		for rcpt in self.recipients:
			if type and rcpt.type != type:
				continue

			recipients.append({"name": rcpt.display_name, "email": rcpt.email})

		return recipients


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Delete multiple Mail Messages based on their names."""

	if isinstance(names, str):
		names = json.loads(names)

	account_ids_map = {}
	for name in names:
		account, id = name.split("|")
		account_ids_map.setdefault(account, []).append(id)

	for account, ids in account_ids_map.items():
		delete_messages(account, ids)

	frappe.msgprint(_("Mail Messages deleted successfully."), alert=True)


@frappe.whitelist()
def reply(source_name: str, target_doc=None) -> "MailQueue":
	"""Reply to the Mail Message."""

	source_doc = frappe.get_doc("Mail Message", source_name)
	return source_doc.reply()


@frappe.whitelist()
def reply_all(source_name: str, target_doc=None) -> "MailQueue":
	"""Reply to all recipients of the Mail Message."""

	source_doc = frappe.get_doc("Mail Message", source_name)
	return source_doc.reply_all()


@frappe.whitelist()
def forward(source_name: str, target_doc=None) -> "MailQueue":
	"""Forward the Mail Message."""

	source_doc = frappe.get_doc("Mail Message", source_name)
	return source_doc.forward()


def fetch_messages(
	account: str,
	filter: dict | None = None,
	position: int = 0,
	limit: int = 50,
	sort: list[dict] | None = None,
) -> tuple[list[dict], int]:
	"""Returns a list of messages and total count based on the provided filter."""

	has_permission_for_user(parse_account(account)[0])

	messages = []

	service = get_email_service(account)
	data = service.query(filter, position, limit, sort)

	ids = data.get("ids", [])
	total = data.get("total", 0)

	messages.extend(get_messages(account, ids=ids))

	return messages[:limit], total


def fetch_threads(account: str, filter: dict | None = None, position: int = 0, limit: int = 50) -> list[dict]:
	"""Returns a list of threads based on the provided filter."""

	has_permission_for_user(parse_account(account)[0])

	service = get_email_service(account)
	ids = service.query_thread(filter, position, limit, fetch_all=False)
	messages = get_messages(account, ids=ids)

	return messages


def fetch_thread(account: str, thread_id: str, sort: Literal["asc", "desc"] = "asc") -> list[dict]:
	"""Returns a list of messages in a thread based on the provided thread ID."""

	has_permission_for_user(parse_account(account)[0])

	service = get_thread_service(account)
	result = service.get([thread_id])
	ids = result.get(thread_id, [])
	messages = get_messages(account, ids=ids)

	return sorted(messages, key=lambda m: m["received_at"], reverse=(sort == "desc"))


def search_messages(
	account: str, filter: dict, position: int = 0, limit: int = 20, sort: list[dict] | None = None
) -> tuple[list[dict], int]:
	"""Returns a list of messages and total count based on the provided search filter."""

	if not account or not filter:
		frappe.throw(_("Account and filter are required."))

	fields = [
		"name",
		"id",
		"subject",
		"preview",
		"recipients",
		"sent_at",
		"received_at",
		"from_name",
		"from_email",
		"thread_id",
		"mailboxes",
		"attachments",
		"seen",
	]

	messages, total = fetch_messages(account, filter=filter, position=position, limit=limit, sort=sort)
	return [{field: message[field] for field in fields} for message in messages], total


def get_messages(account: str, ids: list[str]) -> list[dict]:
	"""Returns a list of messages for the provided IDs in the same order as ids."""

	has_permission_for_user(parse_account(account)[0])

	messages = {}
	ids_to_fetch = []

	for id in ids:
		if message := _get_message_from_cache(account, id):
			messages[id] = message
		else:
			ids_to_fetch.append(id)

	if ids_to_fetch:
		service = get_email_service(account)
		emails = service.get(ids_to_fetch)

		mailbox_map = {mb["id"]: mb["name"] for mb in service.mailboxes}

		for email in emails:
			message = format_message(account, mailbox_map, email)
			_store_message_in_cache(account, message["id"], message)
			messages[message["id"]] = message

	return [messages[id] for id in ids if id in messages]


def get_message_ids(
	account: str, thread_ids: list[str], mailbox_id: str | list[str] | None = None
) -> list[str]:
	"""Returns the message IDs for the given threads."""

	if not account or not thread_ids:
		frappe.throw(_("Account and Thread IDs are required."))

	has_permission_for_user(parse_account(account)[0])

	try:
		thread_service = get_thread_service(account)
		result = thread_service.get(thread_ids)
		ids = [id for _thread_id, ids in result.items() for id in ids]

		if not mailbox_id:
			return ids

		email_service = get_email_service(account)
		emails = email_service.get(ids, properties=["id", "mailboxIds"])
		if isinstance(mailbox_id, str):
			return [email["id"] for email in emails if mailbox_id in email["mailboxIds"]]
		else:
			return [email["id"] for email in emails if not set(mailbox_id).isdisjoint(email["mailboxIds"])]

	except Exception:
		frappe.log_error(_("Failed to fetch message IDs."), frappe.get_traceback(with_context=True))
		frappe.throw(_("Failed to fetch message IDs."))


def delete_messages(account: str, ids: list[str]) -> None:
	"""Delete messages from the server and remove them from the cache."""

	if not account or not ids:
		frappe.throw(_("Account and Mail IDs are required."))

	has_permission_for_user(parse_account(account)[0])

	try:
		service = get_email_service(account)
		service.delete(ids)
		_remove_messages_from_cache(account, ids)
	except Exception:
		frappe.log_error(
			title=_("Failed to delete mail(s)"),
			message=frappe.get_traceback(with_context=True),
		)
		frappe.throw(_("Failed to delete mail(s)."))


def empty_mailbox(account: str, mailbox_id: str) -> None:
	"""Empty the specified mailbox by deleting all messages in it."""

	if not account or not mailbox_id:
		frappe.throw(_("Account and Mailbox ID are required."))

	has_permission_for_user(parse_account(account)[0])

	try:
		service = get_email_service(account)

		while True:
			result = service.query({"inMailbox": mailbox_id}, position=0, limit=service.max_objects_in_get)

			ids = result["ids"]
			if not ids:
				break

			service.delete(ids)
			_remove_messages_from_cache(account, ids)
	except Exception:
		frappe.log_error(
			title=_("Failed to empty mailbox"),
			message=frappe.get_traceback(with_context=True),
		)
		frappe.throw(_("Failed to empty mailbox."))


def move_messages(account: str, ids: list[str], mailbox_id: str) -> None:
	"""Move messages to a different mailbox."""

	if not account or not ids or not mailbox_id:
		frappe.throw(_("Accounts, Mail IDs, and Mailbox ID are required."))

	has_permission_for_user(parse_account(account)[0])

	try:
		emails = [{"id": id, "mailbox_ids": {mailbox_id: True}} for id in ids]
		service = get_email_service(account)
		service.update(emails)
		_remove_messages_from_cache(account, ids)
	except Exception:
		frappe.log_error(
			title=_("Failed to move mail(s) to mailbox"),
			message=frappe.get_traceback(with_context=True),
		)
		frappe.throw(_("Failed to move mail(s) to mailbox."))


def set_seen_status(account: str, ids: list[str], seen: bool = True) -> None:
	"""Set the seen status for messages."""

	if not account or not ids:
		frappe.throw(_("Account and Mail IDs are required."))

	has_permission_for_user(parse_account(account)[0])

	try:
		emails = [{"id": id, "keywords": {"$seen": seen}} for id in ids]
		service = get_email_service(account)
		service.update(emails)

		for id in ids:
			if message := _get_message_from_cache(account, id):
				keywords = json.loads(message["keywords"])
				keywords["$seen"] = bool(seen)

				message["seen"] = cint(seen)
				message["keywords"] = json.dumps(keywords, indent=4)

				_store_message_in_cache(account, message["id"], message)
	except Exception:
		frappe.log_error(
			title=_("Failed to set seen status for mail(s)"),
			message=frappe.get_traceback(with_context=True),
		)
		frappe.throw(_("Failed to set seen status for mail(s)."))


def set_flagged_status(account: str, ids: list[str], flagged: bool = True) -> None:
	"""Set the flagged status for messages."""

	if not account or not ids:
		frappe.throw(_("Account and Mail IDs are required."))

	has_permission_for_user(parse_account(account)[0])

	try:
		emails = [{"id": id, "keywords": {"$flagged": flagged}} for id in ids]
		service = get_email_service(account)
		service.update(emails)

		for id in ids:
			if message := _get_message_from_cache(account, id):
				keywords = json.loads(message["keywords"])
				keywords["$flagged"] = bool(flagged)

				message["flagged"] = cint(flagged)
				message["keywords"] = json.dumps(keywords, indent=4)

				_store_message_in_cache(account, message["id"], message)
	except Exception:
		frappe.log_error(
			title=_("Failed to set flagged status for mail(s)"),
			message=frappe.get_traceback(with_context=True),
		)
		frappe.throw(_("Failed to set flagged status for mail(s)."))


def set_spam_status(account: str, ids: list[str], spam: bool = True) -> None:
	"""Set the spam status for messages."""

	if not account or not ids:
		frappe.throw(_("Account and Mail IDs are required."))

	user = parse_account(account)[0]
	has_permission_for_user(user)

	try:
		connection = get_jmap_connection(user)
		email_service = EmailService(account, connection)
		mailbox_service = MailboxService(account, connection)

		mailbox_id = mailbox_service.get_mailbox_id_by_role(
			"junk" if spam else "inbox", create_if_not_exists=True, raise_exception=True
		)
		emails = [
			{"id": id, "mailbox_ids": {mailbox_id: True}, "keywords": {"$junk": spam, "$notjunk": not spam}}
			for id in ids
		]
		email_service.update(emails)

		_remove_messages_from_cache(account, ids)
	except Exception:
		frappe.log_error(
			title=_("Failed to set spam status for mail(s)"),
			message=frappe.get_traceback(with_context=True),
		)
		frappe.throw(_("Failed to set spam status for mail(s)."))


def fetch_blob(account: str, blob_id: str, name: str | None = None) -> bytes:
	"""Fetch the content of a blob."""

	return fetch_blobs(account, [(blob_id, name)])[blob_id]


def fetch_blobs(account: str, blobs: list[str] | list[tuple[str, str | None]]) -> dict[str, bytes]:
	"""Fetch blobs for the provided blob IDs."""

	if not account:
		frappe.throw(_("Account is required."))

	has_permission_for_user(parse_account(account)[0])

	if isinstance(blobs, list) and all(isinstance(b, str) for b in blobs):
		blobs = [(blob_id, None) for blob_id in blobs]

	result = {}
	blobs_to_fetch = []
	for blob_id, name in blobs:
		if content := _get_blob_from_cache(account, blob_id):
			result[blob_id] = content
		else:
			blobs_to_fetch.append((blob_id, name))

	if not blobs_to_fetch:
		return result

	try:
		service = get_email_service(account)
		fetched_blobs = service.download_blobs_concurrently(blobs_to_fetch)

		for blob_id, content in fetched_blobs.items():
			_store_blob_in_cache(account, blob_id, content)
			result[blob_id] = content

		return result
	except Exception:
		frappe.log_error(
			title=_("Failed to fetch blob(s)"),
			message=frappe.get_traceback(with_context=True),
		)
		frappe.throw(_("Failed to fetch blob(s)."))


def format_message(account: str, mailbox_map: dict, message: dict) -> dict:
	"""Returns a formatted message dictionary for the provided message data."""

	def convert_img_src_from_cid_to_url(html_body: str, cid: str, url: str) -> str:
		"""Convert img src from cid to URL in the HTML body."""

		soup = BeautifulSoup(html_body, "html.parser")
		for img in soup.find_all("img", src=f"cid:{cid}"):
			img["data-cid"] = cid
			img["src"] = url

		return str(soup)

	# Ref: https://github.com/stalwartlabs/stalwart/discussions/2891
	try:
		received_at = parse_iso_datetime(message["receivedAt"])
	except Exception:
		message["receivedAt"] = message["sentAt"] or to_iso8601_z(get_datetime())
		received_at = parse_iso_datetime(message["receivedAt"])

	if not message["sentAt"]:
		message["sentAt"] = message["receivedAt"]

	sent_at = parse_iso_datetime(message["sentAt"])
	formatted_message = {
		"account": account,
		"sent_at": sent_at,
		"creation": sent_at,
		"id": message["id"],
		"size": message["size"],
		"modified": received_at,
		"received_at": received_at,
		"blob_id": message["blobId"],
		"subject": message["subject"],
		"thread_id": message["threadId"],
		"name": f"{account}|{message['id']}",
		"preview": message.get("preview", ""),
		"has_attachment": cint(message["hasAttachment"]),
		"keywords": json.dumps(message["keywords"], indent=4),
		"received_after": time_diff_in_seconds(received_at, sent_at),
	}

	for key in ["sender", "from"]:
		formatted_message[f"{key}_name"] = message[key][0]["name"] if message[key] else None
		formatted_message[f"{key}_email"] = message[key][0]["email"] if message[key] else None

	formatted_message["reply_to"] = []
	if reply_to := message["replyTo"]:
		for rt in reply_to:
			formatted_message["reply_to"].append({"display_name": rt["name"], "email": rt["email"]})

	formatted_message["recipients"] = []
	for key in ["to", "cc", "bcc"]:
		if rcpts := message[key]:
			titled_key = key.title()
			for rcpt in rcpts:
				formatted_message["recipients"].append(
					{"type": titled_key, "display_name": rcpt["name"], "email": rcpt["email"]}
				)

	for key, field in {"htmlBody": "html_body", "textBody": "text_body"}.items():
		value = (
			message.get("bodyValues", {}).get(message[key][0]["partId"], {}).get("value")
			if message.get(key)
			else None
		)
		formatted_message[field] = value

	formatted_message["mailboxes"] = []
	for mailbox_id, value in message["mailboxIds"].items():
		if value:
			formatted_message["mailboxes"].append(
				{
					"mailbox": f"{account}|{mailbox_id}",
					"mailbox_id": mailbox_id,
					"mailbox_name": mailbox_map.get(mailbox_id),
				}
			)

	for key in ["draft", "junk", "seen", "flagged", "answered", "forwarded"]:
		formatted_message[key] = cint(message["keywords"].get(f"${key}", False))

	for key, field in {"messageId": "message_id", "inReplyTo": "in_reply_to"}.items():
		formatted_message[field] = message[key][0] if message[key] else None

	for key, field in {
		"attachments": "attachments",
		"htmlBody": "_html_body",
		"textBody": "_text_body",
	}.items():
		formatted_message[field] = []
		for p in message[key]:
			formatted_message[field].append(
				{
					"part_id": p["partId"],
					"blob_id": p["blobId"],
					"size": p["size"],
					"filename": p["name"],
					"type": p["type"],
					"charset": p["charset"],
					"disposition": p["disposition"],
					"cid": p["cid"] or random_string(10),
					"language": str(p["language"]),
					"location": p["location"],
				}
			)

	for attachment in formatted_message["attachments"]:
		if blob_id := attachment["blob_id"]:
			params = f"account={account}&blob_id={blob_id}"
			if filename := attachment["filename"]:
				params += f"&filename={quote(filename)}"
			attachment["url"] = f"/api/method/mail.api.mail.get_attachment?{params}"

			if attachment["cid"] and formatted_message["html_body"]:
				formatted_message["html_body"] = convert_img_src_from_cid_to_url(
					formatted_message["html_body"],
					attachment["cid"],
					attachment["url"],
				)

	return formatted_message


def _get_message_cache_key(account: str, id: str) -> str:
	"""Returns cache key for message."""

	return f"jmap:message:{account}:{id}"


def _get_blob_cache_key(account: str, blob_id: str) -> str:
	"""Returns cache key for blob content."""

	return f"jmap:blob:{account}:{blob_id}"


def _get_total_cache_key(account: str) -> str:
	"""Returns cache key for total messages."""

	return f"jmap:message:{account}:total"


def _get_message_from_cache(account: str, id: str) -> dict | None:
	"""Returns a message from cache if it exists."""

	cache_key = _get_message_cache_key(account, id)
	return frappe.cache.get_value(cache_key)


def _store_message_in_cache(account: str, id: str, message: dict) -> None:
	"""Store a message in cache with TTL and maintain per-account bucket size."""

	cache_key = _get_message_cache_key(account, id)
	list_key = f"jmap:message:{account}:ids"
	msg_bucket_size = cint(get_mail_config("msg_bucket_size"))

	msg_cache_ttl = cint(get_mail_config("msg_cache_ttl"))
	frappe.cache.set_value(cache_key, message, expires_in_sec=msg_cache_ttl)
	frappe.cache.lpush(list_key, id)

	frappe.cache.ltrim(list_key, 0, msg_bucket_size - 1)

	while frappe.cache.llen(list_key) > msg_bucket_size:
		if oldest_id := frappe.cache.rpop(list_key):
			frappe.cache.delete_key(_get_message_cache_key(account, oldest_id))


def _remove_messages_from_cache(account: str, ids: list[str]) -> None:
	"""Remove a message from cache."""

	for id in ids:
		cache_key = _get_message_cache_key(account, id)
		frappe.cache.delete_value(cache_key)

	list_key = f"jmap:message:{account}:ids"
	for id in ids:
		frappe.cache.lrem(list_key, 0, id)

	if not frappe.cache.llen(list_key):
		frappe.cache.delete_value(list_key)


def _get_blob_from_cache(account: str, blob_id: str) -> bytes | None:
	"""Returns a blob from cache if it exists."""

	cache_key = _get_blob_cache_key(account, blob_id)
	return frappe.cache.get_value(cache_key)


def _store_blob_in_cache(account: str, blob_id: str, content: bytes) -> None:
	"""Store a blob in cache with TTL and maintain per-account bucket size."""

	cache_key = _get_blob_cache_key(account, blob_id)
	list_key = f"jmap:blob:{account}:blob_ids"

	blob_bucket_size = cint(get_mail_config("blob_bucket_size"))
	blob_cache_ttl = cint(get_mail_config("blob_cache_ttl"))

	frappe.cache.set_value(cache_key, content, expires_in_sec=blob_cache_ttl)
	frappe.cache.lpush(list_key, blob_id)

	frappe.cache.ltrim(list_key, 0, blob_bucket_size - 1)

	while frappe.cache.llen(list_key) > blob_bucket_size:
		if oldest_id := frappe.cache.rpop(list_key):
			frappe.cache.delete_key(_get_blob_cache_key(account, oldest_id))


def fetch_changes(account: str, email_state: str | None = None, ctx: dict | None = None) -> None:
	"""Fetch changes from the server and remove MailMessage documents from the cache."""

	ctx = ctx or {}

	logger = get_push_logger()

	current_state = get_sync_state(account, type="email")

	ctx["current_state"] = current_state
	ctx["email_state"] = email_state

	if not current_state:
		logger.info({**ctx, "event": "initializing-email-sync-state"})
		return update_sync_state(account, type="email", state=email_state)

	elif email_state == current_state:
		logger.info({**ctx, "event": "email-state-unchanged"})
		return

	user, account_id = parse_account(account)

	try:
		logger.info({**ctx, "event": "fetching-changes-from-server"})

		connection = get_jmap_connection(user)
		email_service = EmailService(account, connection)
		mailbox_service = MailboxService(account, connection)

		result = email_service.changes(current_state)

		if created_ids := result["created"]:
			logger.info({**ctx, "event": "new-messages-created", "count": len(created_ids)})

			if messages := get_messages(account, ids=created_ids):
				subscribed_mailboxes = set([m["id"] for m in mailbox_service.mailboxes if m["isSubscribed"]])
				logger.debug({**ctx, "subscribed_mailboxes": subscribed_mailboxes})

				disabled_mailboxes = set(
					frappe.db.get_all(
						"Mailbox Settings",
						{"account": account, "disable_push_notification": 1},
						pluck="mailbox_id",
					)
				) | {
					m["id"]
					for m in mailbox_service.mailboxes
					if m["role"] in ["sent", "drafts", "junk", "trash"]
				}
				logger.debug({**ctx, "disabled_mailboxes_for_notification": disabled_mailboxes})

				notify_candidates = []
				mailboxes_to_reload = set()

				for message in messages:
					if message["draft"] or message["seen"]:
						continue

					mailbox_id = None
					is_candidate = False

					for mailbox in message["mailboxes"]:
						if mailbox["mailbox_id"] not in subscribed_mailboxes:
							continue

						mailboxes_to_reload.add(mailbox["mailbox_id"])

						if not is_candidate and mailbox["mailbox_id"] not in disabled_mailboxes:
							mailbox_id = mailbox["mailbox_id"]
							is_candidate = True

					if is_candidate:
						notify_candidates.append((mailbox_id, message))

				logger.debug({**ctx, "notify_candidates_count": len(notify_candidates)})

				max_push_notifications = cint(get_mail_config("max_push_notifications"))
				recent_messages = notify_candidates[:max_push_notifications]

				logger.debug({**ctx, "recent_notify_candidates_count": len(recent_messages)})

				pn = PushNotification("mail")

				if pn.is_enabled():
					logger.info({**ctx, "event": "sending-push-notifications", "count": len(recent_messages)})

					url = frappe.utils.get_url()
					for mailbox_id, message in recent_messages:
						pn.send_notification_to_user(
							user,
							message["from_name"] or message["from_email"],
							message["subject"] or _("[No subject]"),
							f"{url}/mail/account/{account_id}/mailbox/{mailbox_id}/{message['thread_id']}",
							f"{url}/assets/mail/frontend/manifest/manifest-icon-192.maskable.png",
						)
				else:
					logger.info({**ctx, "event": "push-notifications-disabled"})

				if mailboxes_to_reload:
					frappe.publish_realtime("new_mail_created", list(mailboxes_to_reload), user=user)

		if updated_ids := result["updated"]:
			logger.info({**ctx, "event": "messages-updated", "count": len(updated_ids)})
			_remove_messages_from_cache(account, updated_ids)

		if destroyed_ids := result["destroyed"]:
			logger.info({**ctx, "event": "messages-deleted", "count": len(destroyed_ids)})
			_remove_messages_from_cache(account, destroyed_ids)

		new_state = result["newState"]

		ctx["new_state"] = new_state
		logger.info({**ctx, "event": "updating-email-sync-state"})

		update_sync_state(account, type="email", state=new_state)

		if result["hasMoreChanges"]:
			logger.info({**ctx, "event": "more-changes-to-fetch"})
			ctx.pop("current_state", None)
			ctx.pop("email_state", None)
			ctx.pop("new_state", None)

			fetch_changes(account, ctx=ctx)

	except Exception:
		logger.error({**ctx, "event": "fetch-changes-failed"})
		frappe.log_error(
			title=_("Failed to fetch changes"),
			message=frappe.get_traceback(with_context=True),
		)


def locked_fetch_changes(
	account: str, email_state: str | None, lock_id: str, ctx: dict | None = None
) -> None:
	"""Fetch changes for the specified account with a lock to prevent concurrent execution."""

	ctx = ctx or {}

	logger = get_push_logger()

	try:
		logger.info({**ctx, "event": "starting-fetch-changes"})
		fetch_changes(account, email_state, ctx=ctx)
	finally:
		logger.info({**ctx, "event": "releasing-fetch-changes-lock"})
		release_lock(f"fetch_changes:{account}", lock_id)


def enqueue_fetch_changes(account: str, email_state: str | None = None, ctx: dict | None = None) -> None:
	"""Enqueue the fetch_changes job for the specified account."""

	ctx = ctx or {}

	logger = get_push_logger()

	logger.info({**ctx, "event": "enqueueing-fetch-changes"})

	lockname = f"fetch_changes:{account}"
	fetch_lock_timeout = cint(get_mail_config("fetch_lock_timeout"))
	identifier = acquire_lock(lockname, acquire_timeout=0, lock_timeout=fetch_lock_timeout)

	if not identifier:
		logger.info({**ctx, "event": "fetch-changes-lock-not-acquired"})
		return

	ctx["lock_id"] = identifier

	with user_context("Administrator"):
		logger.debug({**ctx, "event": "fetch-changes-lock-acquired"})
		enqueue_job(
			locked_fetch_changes,
			account=account,
			email_state=email_state,
			lock_id=identifier,
			ctx=ctx,
			queue="short",
			enqueue_after_commit=True,
		)


def schedule_fetch_changes() -> None:
	"""Schedule fetch_changes for users who have email accounts configured and haven't had their email state updated in the last 3 hours."""

	USER = frappe.qb.DocType("User")
	USER_SETTINGS = frappe.qb.DocType("User Settings")
	ACCOUNT_SETTINGS = frappe.qb.DocType("Account Settings")

	threshold = add_to_date(now(), hours=-3)

	accounts = (
		frappe.qb.from_(ACCOUNT_SETTINGS)
		.join(USER)
		.on(USER.name == ACCOUNT_SETTINGS.user)
		.join(USER_SETTINGS)
		.on(USER_SETTINGS.user == USER.name)
		.select(ACCOUNT_SETTINGS.account)
		.distinct()
		.where(
			(USER.enabled == 1)
			& (USER_SETTINGS.username != "")
			& (USER_SETTINGS.username.isnotnull())
			& (USER_SETTINGS.skip_schedule_fetch_changes == 0)
			& (
				ACCOUNT_SETTINGS.email_state_last_update.isnull()
				| (ACCOUNT_SETTINGS.email_state_last_update < threshold)
			)
		)
	).run(pluck="account")

	if not accounts:
		return

	req_id = random_string(10)
	logger = get_push_logger()

	logger.info(
		{
			"req_id": req_id,
			"event": "scheduling-fetch-changes",
			"account_count": len(accounts),
		}
	)

	for idx, account in enumerate(accounts, start=1):
		ctx = {"req_id": f"{req_id}-{idx}", "account": account}
		enqueue_fetch_changes(account, ctx=ctx)
