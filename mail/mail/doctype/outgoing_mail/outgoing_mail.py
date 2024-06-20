# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from re import finditer
from email import policy
from uuid_utils import uuid7
from bs4 import BeautifulSoup
from mimetypes import guess_type
from email.message import Message
from dkim import sign as dkim_sign
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.audio import MIMEAudio
from email.mime.image import MIMEImage
from email.encoders import encode_base64
from typing import Optional, TYPE_CHECKING
from frappe.model.document import Document
from urllib.parse import urlparse, parse_qs
from email.mime.multipart import MIMEMultipart
from mail.utils.email_parser import EmailParser
from frappe.utils.file_manager import save_file
from mail.utils.agent import get_random_outgoing_agent
from frappe.utils.password import get_decrypted_password
from email.utils import parseaddr, make_msgid, formataddr, formatdate
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from mail.utils import get_in_reply_to, convert_html_to_text, parsedate_to_datetime
from mail.utils.user import is_mailbox_owner, is_system_manager, get_user_mailboxes
from mail.utils.validation import validate_mail_folder, validate_mailbox_for_outgoing
from frappe.utils import (
	flt,
	now,
	get_datetime_str,
	time_diff_in_seconds,
	validate_email_address,
)

if TYPE_CHECKING:
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class OutgoingMail(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_amended_doc()
		self.validate_folder()
		self.validate_domain()
		self.validate_sender()
		self.validate_reply_to_mail()
		self.validate_recipients()
		self.validate_custom_headers()
		self.load_attachments()
		self.validate_attachments()

		if self.get("_action") == "submit":
			self.set_ip_address()
			self.set_agent()
			self.set_message_id()

			if not self.raw_message:
				self.set_body_html()
				self.set_body_plain()

			self.generate_message()
			self.validate_max_message_size()

	def on_submit(self) -> None:
		self.create_mail_contacts()
		self._db_set(status="Pending", notify_update=True)

		if not self.send_in_batch:
			transfer_mail(outgoing_mail=self)

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

		if self.docstatus == 0:
			self.folder = "Drafts"
		elif self.docstatus == 1 and self.folder == "Drafts":
			self.folder = "Sent"
		elif self.has_value_changed("folder"):
			validate_mail_folder(self.folder, validate_for="outbound")

	def validate_domain(self) -> None:
		"""Validates the domain."""

		if frappe.session.user == "Administrator":
			return

		enabled, verified = frappe.db.get_value(
			"Mail Domain", self.domain_name, ["enabled", "verified"]
		)

		if not enabled:
			frappe.throw(_("Domain {0} is disabled.").format(frappe.bold(self.domain_name)))
		if not verified:
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

		validate_mailbox_for_outgoing(self.sender)

	def validate_reply_to_mail(self) -> None:
		"""Validates the Reply To Mail."""

		if self.reply_to_mail_name:
			if not self.reply_to_mail_type:
				frappe.throw(_("Reply To Mail Type is required."))
			elif self.reply_to_mail_type not in ["Incoming Mail", "Outgoing Mail"]:
				frappe.throw(
					_("{0} must be either Incoming Mail or Outgoing Mail.").format(
						frappe.bold("Reply To Mail Type")
					)
				)

	def validate_recipients(self) -> None:
		"""Validates the recipients."""

		max_recipients = frappe.db.get_single_value(
			"Mail Settings", "max_recipients", cache=True
		)

		if len(self.recipients) > max_recipients:
			frappe.throw(
				_("Recipient limit exceeded ({0}). Maximum {1} recipient(s) allowed.").format(
					frappe.bold(len(self.recipients)), frappe.bold(max_recipients)
				)
			)

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
			max_headers = frappe.db.get_single_value("Mail Settings", "max_headers", cache=True)

			if len(self.custom_headers) > max_headers:
				frappe.throw(
					_(
						"Custom Headers limit exceeded ({0}). Maximum {1} custom header(s) allowed."
					).format(
						frappe.bold(len(self.custom_headers)), frappe.bold(max_headers)
					)
				)

			for header in self.custom_headers:
				if not header.key.upper().startswith("X-"):
					header.key = f"X-{header.key}"

				if header.key.upper().startswith("X-FM-"):
					frappe.throw(
						_("Custom header {0} is not allowed.").format(frappe.bold(header.key))
					)

	def load_attachments(self) -> None:
		"""Loads the attachments."""

		self.attachments = frappe.db.get_all(
			"File",
			fields=["name", "file_name", "file_url", "is_private", "file_size"],
			filters={"attached_to_doctype": self.doctype, "attached_to_name": self.name},
		)

		for attachment in self.attachments:
			attachment.type = "attachment"

	def validate_attachments(self) -> None:
		"""Validates the attachments."""

		if self.attachments:
			mail_settings = frappe.get_cached_doc("Mail Settings")

			if len(self.attachments) > mail_settings.outgoing_max_attachments:
				frappe.throw(
					_("Attachment limit exceeded ({0}). Maximum {1} attachment(s) allowed.").format(
						frappe.bold(len(self.attachments)),
						frappe.bold(mail_settings.outgoing_max_attachments),
					)
				)

			total_attachments_size = 0
			for attachment in self.attachments:
				file_size = flt(attachment.file_size / 1024 / 1024, 3)
				if file_size > mail_settings.outgoing_max_attachment_size:
					frappe.throw(
						_("Attachment size limit exceeded ({0} MB). Maximum {1} MB allowed.").format(
							frappe.bold(file_size), frappe.bold(mail_settings.outgoing_max_attachment_size)
						)
					)

				total_attachments_size += file_size

			if total_attachments_size > mail_settings.outgoing_total_attachments_size:
				frappe.throw(
					_("Attachments size limit exceeded ({0} MB). Maximum {1} MB allowed.").format(
						frappe.bold(total_attachments_size),
						frappe.bold(mail_settings.outgoing_total_attachments_size),
					)
				)

	def set_ip_address(self) -> None:
		"""Sets the IP Address."""

		self.ip_address = frappe.local.request_ip

	def set_agent(self) -> None:
		"""Sets the Agent."""

		outgoing_agent = frappe.db.get_value(
			"Mail Domain", self.domain_name, "outgoing_agent", cache=True
		)
		self.agent = outgoing_agent or get_random_outgoing_agent()

	def set_message_id(self) -> None:
		"""Sets the Message ID."""

		self.message_id = make_msgid(domain=self.domain_name)

	def set_body_html(self) -> None:
		"""Sets the HTML Body."""

		if self.raw_html:
			self.body_html = self.raw_html
			self.raw_html = None

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
				parser = EmailParser(self.raw_message)
				self.raw_html = self.body_html = self.body_plain = self.raw_message = None

				if parser.get_date() > now():
					frappe.throw(_("Invalid date in the email."))

				self.subject = parser.get_subject()
				self.reply_to = parser.get_header("Reply-To")
				self.message_id = parser.get_header("Message-ID") or self.message_id
				self.reply_to_mail_type, self.reply_to_mail_name = get_in_reply_to(
					parser.get_header("In-Reply-To")
				)
				parser.save_attachments(self.doctype, self.name, is_private=True)
				self.body_html, self.body_plain = parser.get_body()

				return parser.message

			message = MIMEMultipart("alternative", policy=policy.SMTP)

			if self.reply_to:
				message["Reply-To"] = self.reply_to

			if self.reply_to_mail_name:
				if in_reply_to := frappe.db.get_value(
					self.reply_to_mail_type, self.reply_to_mail_name, "message_id"
				):
					message["In-Reply-To"] = in_reply_to

			message["From"] = formataddr((self.display_name, self.sender))

			for type in ["To", "Cc", "Bcc"]:
				if recipients := self._get_recipients(type):
					message[type] = recipients

			message["Subject"] = self.subject
			message["Date"] = formatdate(localtime=True)
			message["Message-ID"] = self.message_id

			body_html = self._replace_image_url_with_content_id()
			body_plain = convert_html_to_text(body_html)

			if self.track:
				self.tracking_id = uuid7().hex
				body_html = add_tracking_pixel(body_html, self.tracking_id)

			message.attach(MIMEText(body_plain, "plain", "utf-8", policy=policy.SMTP))
			message.attach(MIMEText(body_html, "html", "utf-8", policy=policy.SMTP))

			return message

		def _add_custom_headers(message: MIMEMultipart | Message) -> None:
			"""Adds the custom headers to the message."""

			if self.custom_headers:
				for header in self.custom_headers:
					message.add_header(header.key, header.value)

		def _add_attachments(message: MIMEMultipart | Message) -> None:
			"""Adds the attachments to the message."""

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
			dkim_selector = frappe.get_cached_value(
				"Mail Domain", self.domain_name, "dkim_selector"
			)
			dkim_private_key = get_decrypted_password(
				"Mail Domain", self.domain_name, "dkim_private_key"
			)
			dkim_signature = dkim_sign(
				message=message.as_string().split("\n", 1)[-1].encode("utf-8"),
				domain=self.domain_name.encode(),
				selector=dkim_selector.encode(),
				privkey=dkim_private_key.encode(),
				include_headers=include_headers,
			)
			dkim_header = dkim_signature.decode().replace("\n", "").replace("\r", "")

			message["DKIM-Signature"] = dkim_header[len("DKIM-Signature: ") :]

		message = _get_message()
		_add_custom_headers(message)
		_add_attachments(message)
		_add_dkim_signature(message)

		self.message = message.as_string()
		self.message_size = len(message.as_bytes())
		self.created_at = get_datetime_str(parsedate_to_datetime(message["Date"]))
		self.submitted_at = now()
		self.submitted_after = time_diff_in_seconds(self.submitted_at, self.created_at)

	def validate_max_message_size(self) -> None:
		"""Validates the maximum message size."""

		message_size = flt(self.message_size / 1024 / 1024, 3)
		max_message_size = frappe.db.get_single_value(
			"Mail Settings", "max_message_size", cache=True
		)

		if message_size > max_message_size:
			frappe.throw(
				_("Message size limit exceeded ({0} MB). Maximum {1} MB allowed.").format(
					frappe.bold(message_size), frappe.bold(max_message_size)
				)
			)

	def create_mail_contacts(self) -> None:
		"""Creates the mail contacts."""

		user = frappe.session.user
		recipient_map = {
			recipient.email: recipient.display_name for recipient in self.recipients
		}

		for email, display_name in recipient_map.items():
			mail_contact = frappe.db.exists("Mail Contact", {"user": user, "email": email})

			if mail_contact:
				current_display_name = frappe.db.get_value(
					"Mail Contact", mail_contact, "display_name"
				)
				if display_name != current_display_name:
					frappe.db.set_value("Mail Contact", mail_contact, "display_name", display_name)
			else:
				doc = frappe.new_doc("Mail Contact")
				doc.user = user
				doc.email = email
				doc.display_name = display_name
				doc.insert()

	def _add_recipients(
		self, type: str, recipients: Optional[str | list[str]] = None
	) -> None:
		"""Adds the recipients."""

		if recipients:
			if isinstance(recipients, str):
				recipients = [recipients]

			for recipient in recipients:
				display_name, email = parseaddr(recipient)

				if not email:
					frappe.throw(_("Invalid format for recipient {0}.").format(frappe.bold(recipient)))

				self.append(
					"recipients", {"type": type, "email": email, "display_name": display_name}
				)

	def _get_recipients(
		self, type: Optional[str] = None, as_list: bool = False
	) -> str | list[str]:
		"""Returns the recipients."""

		recipients = []
		for recipient in self.recipients:
			if type and recipient.type != type:
				continue

			recipients.append(formataddr((recipient.display_name, recipient.email)))

		return recipients if as_list else ", ".join(recipients)

	def _add_attachments(self, attachments: Optional[list[dict]] = None) -> None:
		"""Adds the attachments."""

		if attachments:
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

	def _add_custom_headers(self, headers: Optional[dict] = None) -> None:
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
	) -> Optional[str]:
		"""Returns the attachment content ID."""

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

	def _get_attachment_file_url(self, src: str) -> Optional[str]:
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
	def retry_transfer_mail(self) -> None:
		"""Retries sending the mail."""

		if self.docstatus == 1 and self.status == "Failed":
			kwargs = {}
			if self.send_in_batch:
				kwargs["send_in_batch"] = 0

			kwargs["error_log"] = None
			kwargs["status"] = "Pending"
			self._db_set(**kwargs, commit=True)
			transfer_mail(outgoing_mail=self)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sender(
	doctype: Optional[str] = None,
	txt: Optional[str] = None,
	searchfield: Optional[str] = None,
	start: Optional[int] = 0,
	page_len: Optional[int] = 20,
	filters: Optional[dict] = None,
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
			& (DOMAIN.verified == 1)
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
def reply_to_mail(source_name, target_doc=None) -> "OutgoingMail":
	"""Returns the reply to mail."""

	reply_to_mail_type = "Outgoing Mail"
	source_doc = frappe.get_doc(reply_to_mail_type, source_name)
	target_doc = target_doc or frappe.new_doc("Outgoing Mail")

	target_doc.reply_to_mail_type = source_doc.doctype
	target_doc.reply_to_mail_name = source_name
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

	soup = BeautifulSoup(body_html, "html.parser")
	src = f"{frappe.utils.get_url()}/api/method/mail.api.track.open?id={tracking_id}"
	tracking_pixel = soup.new_tag(
		"img", src=src, width="1", height="1", style="display:none;"
	)

	if not soup.body:
		body_html = f"<html><body>{body_html}</body></html>"
		soup = BeautifulSoup(body_html, "html.parser")

	soup.body.insert(0, tracking_pixel)
	return str(soup)


def create_outgoing_mail(
	sender: str,
	to: str | list[str],
	display_name: Optional[str] = None,
	cc: Optional[str | list[str]] = None,
	bcc: Optional[str | list[str]] = None,
	subject: Optional[str] = None,
	raw_html: Optional[str] = None,
	track: int = 0,
	reply_to: Optional[str | list[str]] = None,
	custom_headers: Optional[dict] = None,
	attachments: Optional[list[dict]] = None,
	raw_message: Optional[str] = None,
	via_api: int = 0,
	send_in_batch: int = 0,
	do_not_save: bool = False,
	do_not_submit: bool = False,
) -> "OutgoingMail":
	"""Creates the outgoing mail."""

	doc: OutgoingMail = frappe.new_doc("Outgoing Mail")
	doc.sender = sender
	doc.display_name = display_name
	doc._add_recipients("To", to)
	doc._add_recipients("Cc", cc)
	doc._add_recipients("Bcc", bcc)
	doc.subject = subject
	doc.raw_html = raw_html
	doc.track = track
	doc.reply_to = reply_to
	doc._add_custom_headers(custom_headers)
	doc.raw_message = raw_message
	doc.via_api = via_api
	doc.send_in_batch = send_in_batch

	if not do_not_save:
		doc.save()
		doc._add_attachments(attachments)
		if not do_not_submit:
			doc.submit()

	return doc


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


def get_permission_query_condition(user: Optional[str]) -> str:
	if not user:
		user = frappe.session.user

	if is_system_manager(user):
		return ""

	if mailboxes := ", ".join(repr(m) for m in get_user_mailboxes(user)):
		return f"(`tabOutgoing Mail`.`sender` IN ({mailboxes})) AND (`tabOutgoing Mail`.`docstatus` != 2)"
	else:
		return "1=0"


def transfer_mail(outgoing_mail: "OutgoingMail") -> None:
	"""Transfers the mail to the agent."""

	if outgoing_mail:
		recipients = [{"type": r.type, "email": r.email} for r in outgoing_mail.recipients]
		request_data = {
			"outgoing_mail": outgoing_mail.name,
			"recipients": recipients,
			"message": outgoing_mail.message,
		}
		create_agent_job(outgoing_mail.agent, "Transfer Mail", request_data=request_data)
		outgoing_mail._db_set(status="Transferring", commit=True)


def transfer_mails() -> None:
	"""Called by the scheduler to transfer the mails in batch."""

	def _get_outgoing_mails() -> list[dict]:
		OM = frappe.qb.DocType("Outgoing Mail")
		return (
			frappe.qb.from_(OM)
			.select(OM.name, OM.agent, OM.message)
			.where((OM.docstatus == 1) & (OM.send_in_batch == 1) & (OM.status == "Pending"))
			.orderby(OM.creation)
		).run(as_dict=True)

	def _create_and_transfer_batch(
		agent: str, outgoing_mails: list, batch_size: int
	) -> None:
		for i in range(0, len(outgoing_mails), batch_size):
			create_agent_job(
				agent, "Transfer Mails", request_data=outgoing_mails[i : i + batch_size]
			)

	def _update_outgoing_mails_status(
		outgoing_mail_list: list[str], commit: bool = False
	) -> None:
		OM = frappe.qb.DocType("Outgoing Mail")
		(
			frappe.qb.update(OM)
			.set(OM.status, "Transferring")
			.where(
				(OM.docstatus == 1)
				& (OM.send_in_batch == 1)
				& (OM.status == "Pending")
				& (OM.name.isin(outgoing_mail_list))
			)
		).run()

		if commit:
			frappe.db.commit()

	if outgoing_mails := _get_outgoing_mails():
		outgoing_mail_list = []
		agent_wise_outgoing_mails = {}
		batch_size = frappe.db.get_single_value("Mail Settings", "max_batch_size", cache=True)

		for mail in outgoing_mails:
			outgoing_mail_list.append(mail["name"])
			agent_wise_outgoing_mails.setdefault(mail.agent, []).append(
				{
					"outgoing_mail": mail.name,
					"message": mail.message,
				}
			)

		del outgoing_mails

		for agent, outgoing_mails in agent_wise_outgoing_mails.items():
			_create_and_transfer_batch(agent, outgoing_mails, batch_size)

		_update_outgoing_mails_status(outgoing_mail_list)


@frappe.whitelist()
def sync_outgoing_mails_status(agents: Optional[str | list] = None) -> None:
	"""Gets the delivery status from agents."""

	if not agents:
		MS = frappe.qb.DocType("Mail Agent")
		OM = frappe.qb.DocType("Outgoing Mail")
		agents = (
			frappe.qb.from_(MS)
			.left_join(OM)
			.on(OM.agent == MS.name)
			.select(MS.name)
			.distinct()
			.where(
				(MS.enabled == 1)
				& (MS.outgoing == 1)
				& (OM.docstatus == 1)
				& (OM.status.isin(["Transferred", "RQ", "Queued", "Deferred"]))
			)
		).run(pluck="name")

	elif isinstance(agents, str):
		agents = [agents]

	for agent in agents:
		create_agent_job(agent, "Sync Outgoing Mails Status")


def transfer_mail_on_end(agent_job: "MailAgentJob") -> None:
	"""Called on the end of the `Transfer Mail` job."""

	if agent_job and agent_job.job_type == "Transfer Mail":
		if agent_job.status in ["Completed", "Failed"]:
			kwargs = {}
			outgoing_mail = None

			if agent_job.status == "Completed":
				data = json.loads(agent_job.response_data)["message"][0]
				outgoing_mail = frappe.get_doc("Outgoing Mail", data["outgoing_mail"])

				transferred_at = now()
				transferred_after = time_diff_in_seconds(transferred_at, outgoing_mail.submitted_at)
				kwargs.update(
					{
						"status": "Transferred",
						"transferred_at": transferred_at,
						"transferred_after": transferred_after,
					}
				)
			else:
				data = json.loads(agent_job.request_data)
				outgoing_mail = frappe.get_doc("Outgoing Mail", data["outgoing_mail"])
				kwargs.update({"status": "Failed", "error_log": agent_job.error_log})

			outgoing_mail._db_set(**kwargs, notify_update=True)


def transfer_mails_on_end(agent_job: "MailAgentJob") -> None:
	"""Called on the end of the `Transfer Mails` job."""

	if agent_job and agent_job.job_type == "Transfer Mails":
		if agent_job.status in ["Completed", "Failed"]:
			outgoing_mails = []
			OM = frappe.qb.DocType("Outgoing Mail")
			query = frappe.qb.update(OM).where(OM.docstatus == 1)

			if agent_job.status == "Completed":
				data = json.loads(agent_job.response_data)["message"]
				outgoing_mails = [d["outgoing_mail"] for d in data]

				transferred_at = now()
				query = (
					query.set(OM.status, "Transferred")
					.set(OM.transferred_at, transferred_at)
					.set(OM.transferred_after, OM.transferred_at - OM.submitted_at)
				)
			else:
				data = json.loads(agent_job.request_data)
				outgoing_mails = [d["outgoing_mail"] for d in data]
				query = query.set(OM.status, "Failed").set(OM.error_log, agent_job.error_log)

			query = query.where(OM.name.isin(outgoing_mails))
			query.run()


def sync_outgoing_mails_status_on_end(agent_job: "MailAgentJob") -> None:
	"""Called on the end of the `Sync Outgoing Mails Status` job."""

	def _validate_data(oml: dict) -> None:
		"""Validates the data."""

		if oml:
			fields = ["outgoing_mail", "status", "recipients"]

			for field in fields:
				if not oml.get(field):
					frappe.throw(_("{0} is required.").format(frappe.bold(field)))
		else:
			frappe.throw(_("Invalid Data."))

	if agent_job and agent_job.job_type == "Sync Outgoing Mails Status":
		if agent_job.status == "Completed":
			if data := json.loads(agent_job.response_data)["message"]:
				for oml in data:
					_validate_data(oml)

					if doc := frappe.get_doc("Outgoing Mail", oml["outgoing_mail"]):
						if oml["status"] not in ["RQ", "Queued"]:
							for recipient in doc.recipients:
								key = (recipient.type, recipient.email)
								oml_recipient = oml["recipients"][str(key)]
								recipient.status = oml_recipient["status"]
								recipient.action_at = oml_recipient["action_at"]
								recipient.action_after = time_diff_in_seconds(
									recipient.action_at, doc.submitted_at
								)
								recipient.retries = oml_recipient["retries"]
								recipient.details = oml_recipient["details"]
								recipient.db_update()

						doc._db_set(status=oml["status"], notify_update=True)
