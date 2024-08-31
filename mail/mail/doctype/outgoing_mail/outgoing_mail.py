# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from re import finditer
from email import policy
from uuid_utils import uuid7
from mail.config import constants
from email.message import Message
from email.mime.text import MIMEText
from frappe.model.document import Document
from mail.utils.cache import get_postmaster
from email.utils import parseaddr, formataddr
from frappe.utils.caching import request_cache
from email.mime.multipart import MIMEMultipart
from mail.rabbitmq import rabbitmq_context
from frappe.utils import flt, now, time_diff_in_seconds
from mail.utils.user import is_mailbox_owner, is_system_manager, get_user_mailboxes
from mail.utils import (
	enqueue_job,
	parse_iso_datetime,
	convert_html_to_text,
)


class OutgoingMail(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_amended_doc()
		self.validate_folder()
		self.load_runtime()
		self.validate_domain()
		self.validate_sender()
		self.validate_in_reply_to()
		self.validate_recipients()
		self.validate_custom_headers()
		self.load_attachments()
		self.validate_attachments()

		if self.get("_action") == "submit" or frappe.flags.bulk_insert:
			self.set_ip_address()
			self.set_message_id()

			if not self.raw_message:
				self.set_body_html()
				self.set_body_plain()

			self.generate_message()
			self.validate_max_message_size()

	def on_submit(self) -> None:
		self.create_mail_contacts()
		self._db_set(status="Pending", notify_update=True)

		if self.via_api and not self.is_newsletter and self.submitted_after <= 5:
			frappe.enqueue_doc("Outgoing Mail", self.name, "transfer_now")

	def on_update_after_submit(self) -> None:
		self.validate_folder()

	def on_trash(self) -> None:
		if self.docstatus != 0 and frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Outgoing Mail."))

	def validate_amended_doc(self) -> None:
		"""Validates the amended document."""

		if self.amended_from:
			frappe.throw(_("Amending {0} is not allowed.").format(frappe.bold("Outgoing Mail")))

	def validate_folder(self) -> None:
		"""Validates the folder"""

		folder = self.folder
		if self.docstatus == 0:
			folder = "Drafts"
		elif folder == "Drafts":
			folder = "Sent"

		if self.get("_action") == "update_after_submit":
			self._db_set(folder=folder, notify_update=True)
		else:
			self.folder = folder

	def sync_with_frontend(self, status) -> None:
		"""Triggered to sync the document with the frontend."""

		if self.via_api:
			if status == "Sent":
				frappe.publish_realtime("outgoing_mail_sent", self.as_dict(), after_commit=True)

	def load_runtime(self) -> None:
		"""Loads the runtime properties."""

		self.runtime = frappe._dict()
		self.runtime.mailbox = frappe.get_cached_doc("Mailbox", self.sender)
		self.runtime.mail_domain = frappe.get_cached_doc("Mail Domain", self.domain_name)
		self.runtime.mail_settings = frappe.get_cached_doc("Mail Settings")

	def validate_domain(self) -> None:
		"""Validates the domain."""

		if frappe.session.user == "Administrator":
			return

		if not self.runtime.mail_domain.enabled:
			frappe.throw(_("Domain {0} is disabled.").format(frappe.bold(self.domain_name)))
		if not self.runtime.mail_domain.is_verified:
			frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(self.domain_name)))

	def validate_sender(self) -> None:
		"""Validates the sender."""

		user = frappe.session.user
		if not is_mailbox_owner(self.sender, user) and not is_system_manager(user):
			frappe.throw(
				_("You are not allowed to send mail from mailbox {0}.").format(
					frappe.bold(self.sender)
				)
			)

		from mail.utils.validation import validate_mailbox_for_outgoing

		validate_mailbox_for_outgoing(self.sender)

	def validate_in_reply_to(self) -> None:
		"""Validates the In Reply To."""

		if not self.in_reply_to_mail_type and not self.in_reply_to_mail_name:
			return

		if not self.in_reply_to_mail_type:
			frappe.throw(_("In Reply To Mail Type is required."))
		elif not self.in_reply_to_mail_name:
			frappe.throw(_("In Reply To Mail Name is required."))
		elif self.in_reply_to_mail_type not in ["Incoming Mail", "Outgoing Mail"]:
			frappe.throw(
				_("{0} must be either Incoming Mail or Outgoing Mail.").format(
					frappe.bold("In Reply To Mail Type")
				)
			)

		from mail.utils import get_in_reply_to

		self.in_reply_to = get_in_reply_to(
			self.in_reply_to_mail_type, self.in_reply_to_mail_name
		)
		if not self.in_reply_to:
			frappe.throw(
				_("In Reply To Mail {0} - {1} does not exist.").format(
					frappe.bold(self.in_reply_to_mail_type), frappe.bold(self.in_reply_to_mail_name)
				)
			)

	def validate_recipients(self) -> None:
		"""Validates the recipients."""

		max_recipients = self.runtime.mail_settings.max_recipients
		if len(self.recipients) > max_recipients:
			frappe.throw(
				_("Recipient limit exceeded ({0}). Maximum {1} recipient(s) allowed.").format(
					frappe.bold(len(self.recipients)), frappe.bold(max_recipients)
				)
			)

		from frappe.utils import validate_email_address

		recipients = []
		for recipient in self.recipients:
			recipient.email = recipient.email.strip().lower()

			if validate_email_address(recipient.email) != recipient.email:
				frappe.throw(
					_("Row #{0}: Invalid recipient {1}.").format(
						recipient.idx, frappe.bold(recipient.email)
					)
				)

			type_email = (recipient.type, recipient.email)

			if type_email in recipients:
				frappe.throw(
					_("Row #{0}: Duplicate recipient {1} of type {2}.").format(
						recipient.idx, frappe.bold(recipient.email), frappe.bold(recipient.type)
					)
				)

			recipients.append(type_email)

	def validate_custom_headers(self) -> None:
		"""Validates the custom headers."""

		if self.custom_headers:
			max_headers = self.runtime.mail_settings.max_headers
			if len(self.custom_headers) > max_headers:
				frappe.throw(
					_(
						"Custom Headers limit exceeded ({0}). Maximum {1} custom header(s) allowed."
					).format(
						frappe.bold(len(self.custom_headers)), frappe.bold(max_headers)
					)
				)

			custom_headers = []
			for header in self.custom_headers:
				if not header.key.upper().startswith("X-"):
					header.key = f"X-{header.key}"

				if header.key.upper().startswith("X-FM-"):
					frappe.throw(
						_("Custom header {0} is not allowed.").format(frappe.bold(header.key))
					)

				if header.key in custom_headers:
					frappe.throw(
						_("Row #{0}: Duplicate custom header {1}.").format(
							header.idx, frappe.bold(header.key)
						)
					)
				else:
					custom_headers.append(header.key)

	def load_attachments(self) -> None:
		"""Loads the attachments."""

		FILE = frappe.qb.DocType("File")
		self.attachments = (
			frappe.qb.from_(FILE)
			.select(FILE.name, FILE.file_name, FILE.file_url, FILE.is_private, FILE.file_size)
			.where(
				(FILE.attached_to_doctype == self.doctype) & (FILE.attached_to_name == self.name)
			)
		).run(as_dict=True)

		for attachment in self.attachments:
			attachment.type = "attachment"

	def validate_attachments(self) -> None:
		"""Validates the attachments."""

		if self.attachments:
			max_attachments = self.runtime.mail_settings.outgoing_max_attachments
			max_attachment_size = self.runtime.mail_settings.outgoing_max_attachment_size
			max_attachments_size = self.runtime.mail_settings.outgoing_total_attachments_size

			if len(self.attachments) > max_attachments:
				frappe.throw(
					_("Attachment limit exceeded ({0}). Maximum {1} attachment(s) allowed.").format(
						frappe.bold(len(self.attachments)),
						frappe.bold(max_attachments),
					)
				)

			total_attachments_size = 0
			for attachment in self.attachments:
				file_size = flt(attachment.file_size / 1024 / 1024, 3)
				if file_size > max_attachment_size:
					frappe.throw(
						_("Attachment size limit exceeded ({0} MB). Maximum {1} MB allowed.").format(
							frappe.bold(file_size), frappe.bold(max_attachment_size)
						)
					)

				total_attachments_size += file_size

			if total_attachments_size > max_attachments_size:
				frappe.throw(
					_("Attachments size limit exceeded ({0} MB). Maximum {1} MB allowed.").format(
						frappe.bold(total_attachments_size),
						frappe.bold(max_attachments_size),
					)
				)

	def set_ip_address(self) -> None:
		"""Sets the IP Address."""

		self.ip_address = frappe.local.request_ip

	def set_message_id(self) -> None:
		"""Sets the Message ID."""

		from email.utils import make_msgid

		self.message_id = make_msgid(domain=self.domain_name)

	def set_body_html(self) -> None:
		"""Sets the HTML Body."""

		self.body_html = self.body_html or ""

		if self.via_api:
			self._correct_attachments_file_url()

	def set_body_plain(self) -> None:
		"""Sets the Plain Body."""

		self.body_plain = convert_html_to_text(self.body_html)

	def generate_message(self) -> None:
		"""Sets the Message."""

		def _get_message() -> MIMEMultipart | Message:
			"""Returns the MIME message."""

			if self.raw_message:
				from mail.utils import get_in_reply_to_mail
				from mail.utils.email_parser import EmailParser

				parser = EmailParser(self.raw_message)

				if parser.get_date() > now():
					frappe.throw(_("Future date is not allowed."))

				if self.via_api:
					if self.runtime.mailbox.override_display_name:
						self.display_name = self.runtime.mailbox.display_name
					if self.runtime.mailbox.override_reply_to:
						if self.runtime.mailbox.reply_to:
							parser.update_header("Reply-To", self.runtime.mailbox.reply_to)
						else:
							del parser["Reply-To"]

				self.body_html = self.body_plain = self.raw_message = None
				parser.update_header("From", formataddr((self.display_name, self.sender)))
				self.subject = parser.get_subject()
				self.reply_to = parser.get_reply_to()
				self.message_id = parser.get_message_id() or self.message_id
				self.in_reply_to = parser.get_in_reply_to()
				self.in_reply_to_mail_type, self.in_reply_to_mail_name = get_in_reply_to_mail(
					self.in_reply_to
				)
				parser.save_attachments(self.doctype, self.name, is_private=True)
				self.body_html, self.body_plain = parser.get_body()

				return parser.message

			from email.utils import formatdate

			message = MIMEMultipart("alternative", policy=policy.SMTP)

			if self.reply_to:
				message["Reply-To"] = self.reply_to

			if self.in_reply_to:
				message["In-Reply-To"] = self.in_reply_to

			message["From"] = formataddr((self.display_name, self.sender))

			for type in ["To", "Cc", "Bcc"]:
				if recipients := self._get_recipients(type):
					message[type] = recipients

			message["Subject"] = self.subject
			message["Date"] = formatdate(localtime=True)
			message["Message-ID"] = self.message_id

			body_html = self._replace_image_url_with_content_id()
			body_plain = convert_html_to_text(body_html)

			if self.runtime.mailbox.track_outgoing_mail:
				self.tracking_id = uuid7().hex
				body_html = add_tracking_pixel(body_html, self.tracking_id)

			message.attach(MIMEText(body_plain, "plain", "utf-8", policy=policy.SMTP))
			message.attach(MIMEText(body_html, "html", "utf-8", policy=policy.SMTP))

			return message

		def _add_headers(message: MIMEMultipart | Message) -> None:
			"""Adds the headers to the message."""

			del message["X-FM-OM"]
			message["X-FM-OM"] = self.name

			if self.custom_headers:
				for header in self.custom_headers:
					message.add_header(header.key, header.value)

		def _add_attachments(message: MIMEMultipart | Message) -> None:
			"""Adds the attachments to the message."""

			from mimetypes import guess_type
			from email.mime.base import MIMEBase
			from email.mime.audio import MIMEAudio
			from email.mime.image import MIMEImage
			from email.encoders import encode_base64

			for attachment in self.attachments:
				file = frappe.get_doc("File", attachment.get("name"))
				content_type = guess_type(file.file_name)[0]

				if content_type is None:
					content_type = "application/octet-stream"

				content = file.get_content()
				maintype, subtype = content_type.split("/", 1)

				if maintype == "text":
					if isinstance(content, str):
						content = content.encode("utf-8")
					part = MIMEText(content, _subtype=subtype, _charset="utf-8", policy=policy.SMTP)

				elif maintype == "image":
					part = MIMEImage(content, _subtype=subtype, policy=policy.SMTP)

				elif maintype == "audio":
					part = MIMEAudio(content, _subtype=subtype, policy=policy.SMTP)

				else:
					part = MIMEBase(maintype, subtype, policy=policy.SMTP)
					part.set_payload(content)
					encode_base64(part)

				part.add_header(
					"Content-Disposition", f'{attachment.type}; filename="{file.file_name}"'
				)
				part.add_header("Content-ID", f"<{attachment.name}>")

				message.attach(part)

		def _add_dkim_signature(message: MIMEMultipart | Message) -> None:
			"""Adds the DKIM signature to the message."""

			from dkim import sign as dkim_sign

			include_headers = [
				b"To",
				b"Cc",
				b"From",
				b"Date",
				b"Subject",
				b"Reply-To",
				b"Message-ID",
				b"In-Reply-To",
			]
			dkim_selector, dkim_private_key = get_dkim_selector_and_private_key(self.domain_name)
			dkim_signature = dkim_sign(
				message=message.as_string().split("\n", 1)[-1].encode("utf-8"),
				domain=self.domain_name.encode(),
				selector=dkim_selector.encode(),
				privkey=dkim_private_key.encode(),
				include_headers=include_headers,
			)
			dkim_header = dkim_signature.decode().replace("\n", "").replace("\r", "")
			message["DKIM-Signature"] = dkim_header[len("DKIM-Signature: ") :]

		from frappe.utils import get_datetime_str
		from mail.utils import parsedate_to_datetime

		message = _get_message()
		_add_headers(message)
		_add_attachments(message)
		_add_dkim_signature(message)

		self.message = message.as_string()
		self.message_size = len(self.message)
		self.created_at = get_datetime_str(parsedate_to_datetime(message["Date"]))
		self.submitted_at = now()
		self.submitted_after = time_diff_in_seconds(self.submitted_at, self.created_at)

	def validate_max_message_size(self) -> None:
		"""Validates the maximum message size."""

		message_size = flt(self.message_size / 1024 / 1024, 3)
		max_message_size = self.runtime.mail_settings.max_message_size

		if message_size > max_message_size:
			frappe.throw(
				_("Message size limit exceeded ({0} MB). Maximum {1} MB allowed.").format(
					frappe.bold(message_size), frappe.bold(max_message_size)
				)
			)

	def create_mail_contacts(self) -> None:
		"""Creates the mail contacts."""

		from mail.mail.doctype.mail_contact.mail_contact import create_mail_contact

		if self.runtime.mailbox.create_mail_contact:
			for recipient in self.recipients:
				create_mail_contact(
					self.runtime.mailbox.user, recipient.email, recipient.display_name
				)

	def update_status(self, status: str | None = None, db_set: bool = True) -> None:
		"""Updates the status based on the recipients status."""

		if not status:
			sent_count = 0
			deferred_count = 0

			for r in self.recipients:
				if r.status == "Sent":
					sent_count += 1
				elif r.status == "Deferred":
					deferred_count += 1

			if sent_count == len(self.recipients):
				status = "Sent"
			elif sent_count > 0:
				status = "Partially Sent"
			elif deferred_count == len(self.recipients):
				status = "Deferred"
			else:
				status = "Bounced"

		self.status = status

		if db_set:
			self._db_set(status=status)

		self.sync_with_frontend(status)

	def _add_recipient(self, type: str, recipient: str | list[str]) -> None:
		"""Adds the recipients."""

		if recipient:
			recipients = [recipient] if isinstance(recipient, str) else recipient
			for rcpt in recipients:
				display_name, email = parseaddr(rcpt)

				if not email:
					frappe.throw(_("Invalid format for recipient {0}.").format(frappe.bold(rcpt)))

				self.append(
					"recipients", {"type": type, "email": email, "display_name": display_name}
				)

	def _get_recipients(
		self, type: str | None = None, as_list: bool = False
	) -> str | list[str]:
		"""Returns the recipients."""

		recipients = []
		for recipient in self.recipients:
			if type and recipient.type != type:
				continue

			recipients.append(formataddr((recipient.display_name, recipient.email)))

		return recipients if as_list else ", ".join(recipients)

	def _add_attachment(self, attachment: dict | list[dict]) -> None:
		"""Adds the attachments."""

		from frappe.utils.file_manager import save_file

		if attachment:
			attachments = [attachment] if isinstance(attachment, dict) else attachment
			for a in attachments:
				filename = a.get("filename")
				content = a["content"]

				kwargs = {
					"dt": self.doctype,
					"dn": self.name,
					"df": "file",
					"fname": filename,
					"content": content,
					"is_private": 1,
					"decode": True,
				}
				file = save_file(**kwargs)

				if filename and filename != file.file_name:
					file.db_set("file_name", filename, update_modified=False)

	def _add_custom_headers(self, headers: dict) -> None:
		"""Adds the custom headers."""

		if headers and isinstance(headers, dict):
			for key, value in headers.items():
				self.append("custom_headers", {"key": key, "value": value})

	def _replace_image_url_with_content_id(self) -> str:
		"""Replaces the image URL with content ID."""

		body_html = self.body_html or ""

		if body_html and self.attachments:
			img_src_pattern = r'<img.*?src=[\'"](.*?)[\'"].*?>'

			for img_src_match in finditer(img_src_pattern, body_html):
				img_src = img_src_match.group(1)

				if content_id := self._get_attachment_content_id(img_src, set_as_inline=True):
					body_html = body_html.replace(img_src, f"cid:{content_id}")

		return body_html

	def _get_attachment_content_id(
		self, file_url: str, set_as_inline: bool = False
	) -> str | None:
		"""Returns the attachment content ID."""

		from urllib.parse import urlparse, parse_qs

		if file_url:
			field = "file_url"
			parsed_url = urlparse(file_url)
			value = parsed_url.path

			if query_params := parse_qs(parsed_url.query):
				if fid := query_params.get("fid", [None])[0]:
					field = "name"
					value = fid

			for attachment in self.attachments:
				if attachment[field] == value:
					if set_as_inline:
						attachment.type = "inline"

					return attachment.name

	def _correct_attachments_file_url(self) -> None:
		"""Corrects the attachments file URL."""

		if self.body_html and self.attachments:
			img_src_pattern = r'<img.*?src=[\'"](.*?)[\'"].*?>'

			for img_src_match in finditer(img_src_pattern, self.body_html):
				img_src = img_src_match.group(1)

				if file_url := self._get_attachment_file_url(img_src):
					self.body_html = self.body_html.replace(img_src, file_url)

	def _get_attachment_file_url(self, src: str) -> str | None:
		"""Returns the attachment file URL."""

		for attachment in self.attachments:
			if src == attachment.file_name:
				return attachment.file_url

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify_update: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, commit=commit)

		if notify_update:
			self.notify_update()

	@frappe.whitelist()
	def retry_failed_mail(self) -> None:
		"""Retries the failed mail."""

		if self.docstatus == 1 and self.status == "Failed":
			self._db_set(status="Pending", error_log=None, commit=True)
			self.transfer_now()

	@frappe.whitelist()
	def retry_bounced_mail(self) -> None:
		"""Retries the bounced mail."""

		if not is_system_manager(frappe.session.user):
			frappe.throw(_("Only System Manager can retry bounced mail."))

		if self.docstatus == 1 and self.status == "Bounced":
			self._db_set(status="Pending", error_log=None, commit=True)
			self.transfer_now()

	@frappe.whitelist()
	def transfer_now(self) -> None:
		"""Transfer the mail to RabbitMQ with the highest priority [3]."""

		if not frappe.flags.force_transfer:
			self.load_from_db()

			# Ensure the document is submitted and in "Pending" status
			if not (self.docstatus == 1 and self.status == "Pending"):
				return

		self._db_set(status="Transferring", commit=True)

		recipients = [formataddr((r.display_name, r.email)) for r in self.recipients]
		data = {
			"outgoing_mail": self.name,
			"recipients": recipients,
			"message": self.message,
		}

		try:
			with rabbitmq_context() as rmq:
				rmq.declare_queue(constants.OUTGOING_MAIL_QUEUE, max_priority=3)
				rmq.publish(constants.OUTGOING_MAIL_QUEUE, json.dumps(data), priority=3)

			transferred_at = now()
			transferred_after = time_diff_in_seconds(transferred_at, self.submitted_at)
			self._db_set(
				status="Transferred",
				transferred_at=transferred_at,
				transferred_after=transferred_after,
				commit=True,
			)
		except Exception:
			error_log = frappe.get_traceback(with_context=False)
			self._db_set(status="Failed", error_log=error_log, commit=True)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sender(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns the sender."""

	MAILBOX = frappe.qb.DocType("Mailbox")
	DOMAIN = frappe.qb.DocType("Mail Domain")
	query = (
		frappe.qb.from_(DOMAIN)
		.left_join(MAILBOX)
		.on(DOMAIN.name == MAILBOX.domain_name)
		.select(MAILBOX.name)
		.where(
			(DOMAIN.enabled == 1)
			& (DOMAIN.is_verified == 1)
			& (MAILBOX.enabled == 1)
			& (MAILBOX.outgoing == 1)
			& (MAILBOX.status == "Active")
			& (MAILBOX[searchfield].like(f"%{txt}%"))
		)
		.offset(start)
		.limit(page_len)
	)

	user = frappe.session.user
	if not is_system_manager(user):
		query = query.where(MAILBOX.user == user)

	return query.run(as_dict=False)


@frappe.whitelist()
def get_default_sender() -> str | None:
	"""Returns the default sender."""

	user = frappe.session.user
	return frappe.db.get_value(
		"Mailbox",
		{
			"user": user,
			"enabled": 1,
			"is_default": 1,
			"outgoing": 1,
			"status": "Active",
		},
		"name",
	)


@frappe.whitelist()
def reply_to_mail(source_name, target_doc=None) -> "OutgoingMail":
	"""Creates an Outgoing Mail as a reply to the given Outgoing Mail."""

	in_reply_to_mail_type = "Outgoing Mail"
	source_doc = frappe.get_doc(in_reply_to_mail_type, source_name)
	target_doc = target_doc or frappe.new_doc("Outgoing Mail")

	target_doc.in_reply_to_mail_type = source_doc.doctype
	target_doc.in_reply_to_mail_name = source_name
	target_doc.sender = source_doc.sender
	target_doc.subject = f"Re: {source_doc.subject}"

	recipient_types = ["To", "Cc"] if frappe.flags.args.all else ["To"]
	for recipient in source_doc.recipients:
		if recipient.type in recipient_types:
			target_doc.append(
				"recipients",
				{
					"type": recipient.type,
					"email": recipient.email,
					"display_name": recipient.display_name,
				},
			)

	return target_doc


def add_tracking_pixel(body_html: str, tracking_id: str) -> str:
	"""Adds the tracking pixel to the HTML body."""

	src = f"{frappe.utils.get_url()}/api/method/mail.api.track.open?id={tracking_id}"
	tracking_pixel = f'<img src="{src}" width="1" height="1" style="display:none;">'

	if "<body>" in body_html:
		body_html = body_html.replace("<body>", f"<body>{tracking_pixel}", 1)
	else:
		body_html = f"<html><body>{tracking_pixel}{body_html}</body></html>"

	return body_html


@request_cache
def get_dkim_selector_and_private_key(domain_name: str) -> tuple[str, str]:
	"""Returns the DKIM selector and private key for the given domain."""

	mail_domain = frappe.get_cached_doc("Mail Domain", domain_name)
	return mail_domain.dkim_selector, mail_domain.get_password("dkim_private_key")


def create_outgoing_mail(
	sender: str,
	to: str | list[str],
	display_name: str | None = None,
	cc: str | list[str] | None = None,
	bcc: str | list[str] | None = None,
	subject: str | None = None,
	body_html: str | None = None,
	reply_to: str | list[str] | None = None,
	in_reply_to_mail_type: str | None = None,
	in_reply_to_mail_name: str | None = None,
	custom_headers: dict | None = None,
	attachments: list[dict] | None = None,
	raw_message: str | None = None,
	via_api: int = 0,
	is_newsletter: int = 0,
	do_not_save: bool = False,
	do_not_submit: bool = False,
) -> "OutgoingMail":
	"""Creates the outgoing mail."""

	doc: OutgoingMail = frappe.new_doc("Outgoing Mail")
	doc.sender = sender
	doc.display_name = display_name
	doc._add_recipient("To", to)
	doc._add_recipient("Cc", cc)
	doc._add_recipient("Bcc", bcc)
	doc.subject = subject
	doc.body_html = body_html
	doc.reply_to = reply_to
	doc.in_reply_to_mail_type = in_reply_to_mail_type
	doc.in_reply_to_mail_name = in_reply_to_mail_name
	doc._add_custom_headers(custom_headers)
	doc.raw_message = raw_message
	doc.via_api = via_api
	doc.is_newsletter = is_newsletter

	if via_api and not is_newsletter:
		user = frappe.session.user
		if sender not in get_user_mailboxes(user, "Outgoing"):
			from mail.utils.cache import get_user_default_mailbox

			doc.sender = get_user_default_mailbox(user)

	if not do_not_save:
		doc.save()
		doc._add_attachment(attachments)
		if not do_not_submit:
			doc.submit()

	return doc


def get_outgoing_mail_for_bulk_insert(**kwargs) -> "OutgoingMail":
	frappe.flags.bulk_insert = True

	doc = create_outgoing_mail(**kwargs, do_not_save=True)
	mailbox = frappe.get_cached_doc("Mailbox", doc.sender)
	doc.domain_name = mailbox.domain_name
	doc.display_name = doc.display_name or mailbox.display_name
	doc.reply_to = doc.reply_to or mailbox.reply_to

	doc.autoname()
	doc.validate()

	for recipient in doc.recipients:
		recipient.docstatus = 1
		recipient.parent = doc.name
		recipient.name = str(uuid7())

	doc.docstatus = 1
	doc.folder = "Sent"
	doc.status = "Pending"

	return doc


@frappe.whitelist()
def delete_outgoing_mails(mailbox: str) -> None:
	"""Deletes the outgoing mails for the given mailbox."""

	if not is_system_manager(frappe.session.user):
		frappe.throw(_("Only System Manager can delete Outgoing Mails."))

	if mailbox:
		frappe.db.delete("Outgoing Mail", {"sender": mailbox})


def has_permission(doc: "Document", ptype: str, user: str) -> bool:
	if doc.doctype != "Outgoing Mail":
		return False

	user_is_system_manager = is_system_manager(user)
	user_is_mailbox_user = is_mailbox_owner(doc.sender, user)

	if ptype == "create":
		return True
	elif ptype in ["write", "cancel"]:
		return user_is_system_manager or user_is_mailbox_user
	else:
		return user_is_system_manager or (user_is_mailbox_user and doc.docstatus != 2)


def get_permission_query_condition(user: str | None = None) -> str:
	if not user:
		user = frappe.session.user

	if is_system_manager(user):
		return ""

	if mailboxes := ", ".join(repr(m) for m in get_user_mailboxes(user)):
		return f"(`tabOutgoing Mail`.`sender` IN ({mailboxes})) AND (`tabOutgoing Mail`.`docstatus` != 2)"
	else:
		return "1=0"


def transfer_mails() -> None:
	"""Transfers the mails to RabbitMQ."""

	def get_mails_to_transfer(limit: int) -> list[dict]:
		"""Returns the mails to transfer."""

		from frappe.query_builder.functions import GroupConcat

		OM = frappe.qb.DocType("Outgoing Mail")
		MR = frappe.qb.DocType("Mail Recipient")
		return (
			frappe.qb.from_(OM)
			.join(MR)
			.on(OM.name == MR.parent)
			.select(
				OM.name,
				OM.is_newsletter,
				OM.domain_name,
				OM.message,
				GroupConcat(MR.email).as_("recipients"),
			)
			.where((OM.docstatus == 1) & (OM.status == "Pending"))
			.groupby(OM.name, OM.is_newsletter, OM.domain_name, OM.message)
			.orderby(OM.submitted_at)
			.limit(limit)
		).run(as_dict=True)

	def update_outgoing_mails(
		outgoing_mails: list, current_status: str, commit: bool = False, **kwargs
	) -> None:
		"""Updates the outgoing mails."""

		OM = frappe.qb.DocType("Outgoing Mail")
		query = frappe.qb.update(OM).where(
			(OM.docstatus == 1) & (OM.status == current_status) & (OM.name.isin(outgoing_mails))
		)

		for field, value in kwargs.items():
			query = query.set(OM[field], value)

		query.run()

		if commit:
			frappe.db.commit()

	import time
	from mail.utils.cache import get_root_domain_name

	max_failures = 3
	total_failures = 0
	max_batch_size = (
		frappe.db.get_single_value("Mail Settings", "max_batch_size", cache=True) or 1000
	)
	root_domain_name = get_root_domain_name()

	while total_failures < max_failures:
		current_status = "Pending"
		mails = get_mails_to_transfer(limit=max_batch_size)

		if not mails:
			break

		outgoing_mails = [mail["name"] for mail in mails]
		update_outgoing_mails(
			outgoing_mails,
			current_status=current_status,
			status="Transferring",
			error_log=None,
			commit=True,
		)
		current_status = "Transferring"

		try:
			with rabbitmq_context() as rmq:
				rmq.declare_queue(constants.OUTGOING_MAIL_QUEUE, max_priority=3)

				for mail in mails:
					priority = 1
					if mail.is_newsletter:
						priority = 0
					elif mail.domain_name == root_domain_name:
						priority = 2

					data = {
						"outgoing_mail": mail["name"],
						"recipients": mail["recipients"].split(","),
						"message": mail["message"],
					}
					rmq.publish(constants.OUTGOING_MAIL_QUEUE, json.dumps(data), priority=priority)

			frappe.db.sql(
				"""
				UPDATE `tabOutgoing Mail`
				SET
					status = %s,
					error_log = NULL,
					transferred_at = %s,
					transferred_after = TIMESTAMPDIFF(SECOND, `submitted_at`, `transferred_at`)
				WHERE
					docstatus = 1 AND
					status = %s AND
					name IN %s
				""",
				("Transferred", now(), current_status, tuple(outgoing_mails)),
			)
			current_status = "Transferred"
		except Exception:
			total_failures += 1
			error_log = frappe.get_traceback(with_context=False)
			frappe.log_error(title="Transfer Mails", message=error_log)
			update_outgoing_mails(
				outgoing_mails, current_status=current_status, status="Failed", error_log=error_log
			)
			current_status = "Failed"

			if total_failures < max_failures:
				time.sleep(5)


def get_outgoing_mails_status() -> None:
	"""Gets the outgoing mails status from RabbitMQ."""

	def has_unsynced_outgoing_mails() -> bool:
		"""Returns True if there are unsynced outgoing mails."""

		OM = frappe.qb.DocType("Outgoing Mail")
		mails = (
			frappe.qb.from_(OM)
			.select(OM.name)
			.distinct()
			.where((OM.docstatus == 1) & (OM.status.isin(["Transferred", "Queued", "Deferred"])))
			.limit(1)
		).run(pluck="name")

		return bool(mails)

	def queue_ok(agent: str, data: dict) -> None:
		"""Updates Queue ID in Outgoing Mail."""

		frappe.db.set_value(
			"Outgoing Mail",
			data["outgoing_mail"],
			{"status": "Queued", "agent": agent, "queue_id": data["queue_id"]},
		)

	def undelivered(data: dict) -> None:
		"""Updates Outgoing Mail status to Deferred or Bounced."""

		try:
			outgoing_mail = data.get("outgoing_mail")
			queue_id = data["queue_id"]
			hook = data["hook"]
			rcpt_to = data["rcpt_to"]
			retries = data["retries"]
			action_at = parse_iso_datetime(data["action_at"])

			doc = frappe.get_doc(
				"Outgoing Mail",
				outgoing_mail if outgoing_mail else {"queue_id": queue_id},
				for_update=True,
			)
			recipients = {
				parseaddr(recipient["original"])[1]: recipient for recipient in rcpt_to
			}
			status = "Deferred" if hook == "deferred" else "Bounced"

			for recipient in doc.recipients:
				if recipient.email in recipients:
					recipient.status = status
					recipient.retries = retries
					recipient.action_at = action_at
					recipient.action_after = time_diff_in_seconds(
						recipient.action_at, doc.transferred_at
					)
					recipient.details = json.dumps(recipients[recipient.email], indent=4)
					recipient.db_update()

			doc.update_status(db_set=False)
			doc.db_update()

		except Exception:
			frappe.log_error(
				title="Error Updating Outgoing Mail Status", message=frappe.get_traceback()
			)

	def delivered(data: dict) -> None:
		"""Updates Outgoing Mail status to Sent or Partially Sent."""

		try:
			outgoing_mail = data.get("outgoing_mail")
			queue_id = data["queue_id"]
			retries = data["retries"]
			action_at = parse_iso_datetime(data["action_at"])
			host, ip, response, delay, port, mode, ok_recips, secured, verified = data["params"]

			doc = frappe.get_doc(
				"Outgoing Mail",
				outgoing_mail if outgoing_mail else {"queue_id": queue_id},
				for_update=True,
			)
			recipients = [parseaddr(recipient["original"])[1] for recipient in ok_recips]

			for recipient in doc.recipients:
				if recipient.email in recipients:
					recipient.status = "Sent"
					recipient.retries = retries
					recipient.action_at = action_at
					recipient.action_after = time_diff_in_seconds(
						recipient.action_at, doc.transferred_at
					)
					recipient.details = json.dumps(
						{
							"host": host,
							"ip": ip,
							"response": response,
							"delay": delay,
							"port": port,
							"mode": mode,
							"secured": secured,
							"verified": verified,
						},
						indent=4,
					)
					recipient.db_update()

				doc.update_status(db_set=False)
				doc.db_update()

		except Exception:
			frappe.log_error(
				title="Error Updating Outgoing Mail Status", message=frappe.get_traceback()
			)

	if not has_unsynced_outgoing_mails():
		return

	try:
		with rabbitmq_context() as rmq:
			rmq.declare_queue(constants.OUTGOING_MAIL_STATUS_QUEUE, max_priority=3)

			while True:
				result = rmq.basic_get(constants.OUTGOING_MAIL_STATUS_QUEUE)

				if result:
					method, properties, body = result
					if body:
						data = json.loads(body)
						hook = data["hook"]

						if hook == "queue_ok":
							queue_ok(properties.app_id, data)
						elif hook in ["bounce", "deferred"]:
							undelivered(data)
						elif hook == "delivered":
							delivered(data)

					rmq.channel.basic_ack(delivery_tag=method.delivery_tag)
				else:
					break
	except Exception:
		frappe.log_error(
			title="Get Outgoing Mails Status",
			message=frappe.get_traceback(with_context=False),
		)


def process_newsletter_queue(batch_size: int = 1000) -> None:
	"""Processes the newsletter queue."""

	from frappe.model.document import bulk_insert

	batch_size = min(batch_size, 1000)

	while True:
		documents = []
		delivery_tags = []

		with rabbitmq_context() as rmq:
			rmq.declare_queue(constants.NEWSLETTER_QUEUE)

			for x in range(batch_size):
				result = rmq.basic_get(constants.NEWSLETTER_QUEUE)

				if not result:
					break

				method, properties, body = result
				if body:
					mail = json.loads(body)
					mail["is_newsletter"] = 1
					doc = get_outgoing_mail_for_bulk_insert(**mail)
					documents.append(doc)
					delivery_tags.append(method.delivery_tag)

			if not documents:
				break

			try:
				bulk_insert("Outgoing Mail", documents)
				frappe.db.commit()

				if delivery_tags:
					rmq.channel.basic_ack(delivery_tag=delivery_tags[-1], multiple=True)
			except Exception:
				if delivery_tags:
					rmq.channel.basic_nack(delivery_tag=delivery_tags[-1], multiple=True, requeue=True)

				frappe.log_error(title="Process Newsletter Queue", message=frappe.get_traceback())


def enqueue_transfer_mails() -> None:
	"Called by the scheduler to enqueue the `transfer_mails` job."

	frappe.session.user = get_postmaster()
	enqueue_job(transfer_mails, queue="long")


@frappe.whitelist()
def enqueue_get_outgoing_mails_status() -> None:
	"Called by the scheduler to enqueue the `get_outgoing_mails_status` job."

	frappe.session.user = get_postmaster()
	enqueue_job(get_outgoing_mails_status, queue="long")


def enqueue_process_newsletter_queue() -> None:
	"Called by the scheduler to enqueue the `process_newsletter_queue` job."

	enqueue_job(process_newsletter_queue, queue="long")
