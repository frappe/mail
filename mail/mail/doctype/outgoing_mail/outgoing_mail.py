# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from re import finditer
from uuid_utils import uuid7
from bs4 import BeautifulSoup
from mimetypes import guess_type
from dkim import sign as dkim_sign
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.audio import MIMEAudio
from email.mime.image import MIMEImage
from frappe.core.utils import html2text
from email.encoders import encode_base64
from typing import Optional, TYPE_CHECKING
from frappe.model.document import Document
from urllib.parse import urlparse, parse_qs
from email.mime.multipart import MIMEMultipart
from frappe.utils.file_manager import save_file
from frappe.utils.password import get_decrypted_password
from email.utils import parseaddr, make_msgid, formataddr, formatdate
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from frappe.utils import (
	flt,
	now,
	get_datetime_str,
	time_diff_in_seconds,
	validate_email_address,
)
from mail.utils import (
	is_mailbox_owner,
	is_system_manager,
	get_user_mailboxes,
	parsedate_to_datetime,
	get_random_outgoing_agent,
	validate_mailbox_for_outgoing,
)


if TYPE_CHECKING:
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class OutgoingMail(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_domain()
		self.validate_sender()
		self.validate_amended_doc()
		self.validate_recipients()
		self.validate_custom_headers()
		self.load_attachments()
		self.validate_attachments()

		if self.get("_action") == "submit":
			self.set_ip_address()
			self.set_agent()
			self.set_body_html()
			self.set_body_plain()
			self.set_message_id()
			self.set_original_message()
			self.validate_max_message_size()

	def on_submit(self) -> None:
		self.create_mail_contacts()
		self._db_set(status="Pending", notify_update=True)

		if not self.send_in_batch:
			self.transfer_mail()

	def on_trash(self) -> None:
		if self.docstatus != 0 and frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Outgoing Mail."))

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

	def validate_amended_doc(self) -> None:
		"""Validates the amended document."""

		if self.amended_from:
			frappe.throw(_("Amending {0} is not allowed.").format(frappe.bold("Outgoing Mail")))

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
		for r in self.recipients:
			r.recipient = r.recipient.strip().lower()

			if validate_email_address(r.recipient) != r.recipient:
				frappe.throw(
					_("Row #{0}: Invalid recipient {1}.").format(r.idx, frappe.bold(r.recipient))
				)

			tr = (r.type, r.recipient)

			if tr in recipients:
				frappe.throw(
					_("Row #{0}: Duplicate recipient {1} of type {2}.").format(
						r.idx, frappe.bold(r.recipient), frappe.bold(r.type)
					)
				)

			recipients.append(tr)

	def validate_custom_headers(self) -> None:
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
				if header.key.startswith("X-FM-"):
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

	def set_body_html(self) -> None:
		"""Sets the HTML Body."""

		if self.use_raw_html:
			self.body_html = self.raw_html

		self.raw_html = ""
		self.body_html = self.body_html or ""

		if self.via_api:
			self._correct_attachments_file_url()

	def set_body_plain(self) -> None:
		"""Sets the Plain Body."""

		self.body_plain = html2text(self.body_html)

	def set_message_id(self) -> None:
		"""Sets the Message ID."""

		self.message_id = make_msgid(domain=self.domain_name)

	def set_original_message(self) -> None:
		"""Sets the Original Message."""

		def _get_message() -> "MIMEMultipart":
			"""Returns the MIME message."""

			message = MIMEMultipart("alternative")
			display_name = frappe.get_cached_value("Mailbox", self.sender, "display_name")
			message["From"] = (
				"{0} <{1}>".format(display_name, self.sender) if display_name else self.sender
			)
			message["To"] = self._get_recipients(type="To")
			message["Cc"] = self._get_recipients(type="Cc")
			message["Bcc"] = self._get_recipients(type="Bcc")
			message["Subject"] = self.subject
			message["Date"] = formatdate(localtime=True)
			message["Message-ID"] = self.message_id

			body_html = self._replace_image_url_with_content_id()
			body_plain = html2text(body_html)
			message.attach(MIMEText(body_plain, "plain", "utf-8"))

			if self.track:
				self.tracking_id = uuid7().hex
				body_html = add_tracking_pixel(body_html, self.tracking_id)

			message.attach(MIMEText(body_html, "html", "utf-8"))

			return message

		def _add_custom_headers(message: "MIMEMultipart") -> None:
			"""Adds the custom headers to the message."""

			if self.custom_headers:
				for header in self.custom_headers:
					message.add_header(header.key, header.value)

		def _add_attachments(message: "MIMEMultipart") -> None:
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
					part = MIMEText(content, _subtype=subtype, _charset="utf-8")

				elif maintype == "image":
					part = MIMEImage(content, _subtype=subtype)

				elif maintype == "audio":
					part = MIMEAudio(content, _subtype=subtype)

				else:
					part = MIMEBase(maintype, subtype)
					part.set_payload(content)
					encode_base64(part)

				part.add_header(
					"Content-Disposition", f'{attachment.type}; filename="{file.file_name}"'
				)
				part.add_header("Content-ID", f"<{attachment.name}>")

				message.attach(part)

		def _add_dkim_signature(message: "MIMEMultipart") -> None:
			"""Adds the DKIM signature to the message."""

			headers = [
				b"To",
				b"From",
				b"Date",
				b"Subject",
				b"Reply-To",
				b"Message-ID",
			]
			dkim_selector = frappe.get_cached_value(
				"Mail Domain", self.domain_name, "dkim_selector"
			)
			dkim_private_key = get_decrypted_password(
				"Mail Domain", self.domain_name, "dkim_private_key"
			)
			signature = dkim_sign(
				message=message.as_string().split("\n", 1)[-1].encode("utf-8"),
				domain=self.domain_name.encode(),
				selector=dkim_selector.encode(),
				privkey=dkim_private_key.encode(),
				include_headers=headers,
			)
			message["DKIM-Signature"] = signature[len("DKIM-Signature: ") :].decode()

		message = _get_message()
		_add_custom_headers(message)
		_add_attachments(message)
		_add_dkim_signature(message)

		self.original_message = message.as_string()
		self.message_size = len(message.as_bytes())
		self.created_at = get_datetime_str(parsedate_to_datetime(message["Date"]))

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
		recipient_map = {r.recipient: r.display_name for r in self.recipients}

		for recipient, display_name in recipient_map.items():
			mail_contact = frappe.db.exists("Mail Contact", {"user": user, "email": recipient})

			if mail_contact:
				current_display_name = frappe.db.get_value(
					"Mail Contact", mail_contact, "display_name"
				)
				if display_name != current_display_name:
					frappe.db.set_value("Mail Contact", mail_contact, "display_name", display_name)
			else:
				doc = frappe.new_doc("Mail Contact")
				doc.user = user
				doc.email = recipient
				doc.display_name = display_name
				doc.insert()

	def transfer_mail(self) -> None:
		"""Sends the mail."""

		request_data = {
			"outgoing_mail": self.name,
			"message": self.original_message,
		}
		create_agent_job(self.agent, "Transfer Mail", request_data=request_data)

	def _add_recipients(
		self, type: str, recipients: Optional[str | list[str]] = None
	) -> None:
		"""Adds the recipients."""

		if recipients:
			if isinstance(recipients, str):
				recipients = [recipients]

			for r in recipients:
				display_name, recipient = parseaddr(r)

				if not recipient:
					frappe.throw(_("Invalid format for recipient {0}.").format(frappe.bold(r)))

				self.append(
					"recipients", {"type": type, "recipient": recipient, "display_name": display_name}
				)

	def _get_recipients(
		self, type: Optional[str] = None, as_list: bool = False
	) -> str | list[str]:
		"""Returns the recipients."""

		recipients = []
		for r in self.recipients:
			if type and r.type != type:
				continue

			recipients.append(formataddr((r.display_name, r.recipient)))

		return recipients if as_list else ", ".join(recipients)

	def _add_attachments(self, attachments: Optional[dict | list[dict]] = None) -> None:
		"""Adds the attachments."""

		if attachments:
			if isinstance(attachments, dict):
				attachments = [attachments]

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

	def _add_custom_headers(self, headers: Optional[dict | list[dict]] = None) -> None:
		"""Adds the custom headers."""

		if headers:
			if isinstance(headers, dict):
				headers = [headers]

			for h in headers:
				self.append("custom_headers", h)

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
			self.transfer_mail()


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
				& (OM.status.isin(["Transferred", "Queued", "Deferred"]))
			)
		).run(pluck="name")

	elif isinstance(agents, str):
		agents = [agents]

	for agent in agents:
		create_agent_job(agent, "Sync Outgoing Mails Status")


def update_outgoing_mails_status(agent_job: "MailAgentJob") -> None:
	"""Called by the Mail Agent Job to update the outgoing mails status."""

	if agent_job and agent_job.job_type in ["Transfer Mail", "Transfer Mails"]:
		data = json.loads(agent_job.request_data)

		if isinstance(data, dict):
			if agent_job.status == "Running":
				outgoing_mail = frappe.get_doc("Outgoing Mail", data.get("outgoing_mail"))
				return outgoing_mail._db_set(status="Transferring", commit=True, notify_update=True)

			data = [data]

		if agent_job.status == "Failed":
			OM = frappe.qb.DocType("Outgoing Mail")
			outgoing_mails = [d["outgoing_mail"] for d in data]
			(
				frappe.qb.update(OM)
				.set(OM.status, "Failed")
				.set(OM.error_log, agent_job.error_log)
				.where((OM.docstatus == 1) & (OM.name.isin(outgoing_mails)))
			).run()

		elif agent_job.status == "Completed":
			OM = frappe.qb.DocType("Outgoing Mail")
			outgoing_mails = [d["outgoing_mail"] for d in data]
			transferred_at = now()
			(
				frappe.qb.update(OM)
				.set(OM.status, "Transferred")
				.set(OM.transferred_at, transferred_at)
				.set(OM.transferred_after, OM.transferred_at - OM.created_at)
				.where((OM.docstatus == 1) & (OM.name.isin(outgoing_mails)))
			).run()


def update_outgoing_mails_delivery_status(agent_job: "MailAgentJob") -> None:
	"""Called by the Mail Agent Job to update the outgoing mails delivery status."""

	def _validate_data(data: dict) -> None:
		"""Validates the data."""

		if data:
			fields = ["outgoing_mail", "status", "recipients"]

			for field in fields:
				if not data.get(field):
					frappe.throw(_("{0} is required.").format(frappe.bold(field)))
		else:
			frappe.throw(_("Invalid Data."))

	if agent_job and agent_job.job_type == "Sync Outgoing Mails Status":
		if agent_job.status == "Completed":
			if data := json.loads(agent_job.response_data)["message"]:
				for oml in data:
					_validate_data(oml)

					if doc := frappe.get_doc("Outgoing Mail", oml["outgoing_mail"]):
						if oml["status"] != "Queued":
							for r in doc.recipients:
								key = (r.type, r.recipient)
								oml_recipient = oml["recipients"][str(key)]
								r.status = oml_recipient["status"]
								r.action_at = oml_recipient["action_at"]
								r.action_after = time_diff_in_seconds(r.action_at, doc.created_at)
								r.retries = oml_recipient["retries"]
								r.details = oml_recipient["details"]
								r.db_update()

						doc._db_set(status=oml["status"], notify_update=True)


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


def transfer_mails() -> None:
	"""Sends the mails in batch."""

	def _get_outgoing_mails() -> list[dict]:
		OM = frappe.qb.DocType("Outgoing Mail")
		return (
			frappe.qb.from_(OM)
			.select(OM.name, OM.agent, OM.original_message)
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

	def _update_outgoing_mails_status(oms: list[str], commit: bool = False) -> None:
		OM = frappe.qb.DocType("Outgoing Mail")
		(
			frappe.qb.update(OM)
			.set(OM.status, "Transferring")
			.where((OM.docstatus == 1) & (OM.name.isin(oms)))
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
					"message": mail.original_message,
				}
			)

		for agent, outgoing_mails in agent_wise_outgoing_mails.items():
			_create_and_transfer_batch(agent, outgoing_mails, batch_size)

		_update_outgoing_mails_status(outgoing_mail_list)


def create_outgoing_mail(
	sender: str,
	subject: str,
	to: Optional[str | list[str]],
	cc: Optional[str | list[str]],
	bcc: Optional[str | list[str]],
	raw_html: Optional[str] = None,
	track: int = 0,
	attachments: Optional[list[dict]] = None,
	custom_headers: Optional[dict | list[dict]] = None,
	via_api: int = 0,
	send_in_batch: int = 0,
	do_not_save: bool = False,
	do_not_submit: bool = False,
) -> "OutgoingMail":
	doc = frappe.new_doc("Outgoing Mail")
	doc.sender = sender
	doc.subject = subject
	doc.raw_html = raw_html
	doc.track = track
	doc.via_api = via_api
	doc.send_in_batch = send_in_batch
	doc._add_recipients("To", to)
	doc._add_recipients("Cc", cc)
	doc._add_recipients("Bcc", bcc)
	doc._add_custom_headers(custom_headers)

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
