# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from uuid import uuid4
from re import finditer
from bs4 import BeautifulSoup
from mimetypes import guess_type
from dkim import sign as dkim_sign
from json import loads as json_loads
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.audio import MIMEAudio
from email.mime.image import MIMEImage
from frappe.core.utils import html2text
from email.encoders import encode_base64
from typing import Optional, TYPE_CHECKING
from frappe.model.document import Document
from email.mime.multipart import MIMEMultipart
from email.utils import make_msgid, formatdate
from frappe.utils.password import get_decrypted_password
from frappe.utils import flt, now, get_datetime_str, time_diff_in_seconds
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from mail.utils import (
	get_outgoing_agent,
	parsedate_to_datetime,
	validate_mailbox_for_outgoing,
)


if TYPE_CHECKING:
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class OutgoingMail(Document):
	def validate(self) -> None:
		self.validate_domain()
		self.validate_sender()
		self.validate_amended_doc()
		self.validate_recipients()
		self.validate_body_html()
		self.load_attachments()
		self.validate_attachments()

		if self.get("_action") == "submit":
			self.set_from_ip()
			self.set_agent()
			self.validate_use_raw_html()
			self.set_body_plain()
			self.set_message_id()
			self.set_tracking_id()
			self.set_original_message()
			self.validate_max_message_size()

	def on_submit(self) -> None:
		self.create_mail_contacts()
		self.send_mail()

	def on_trash(self) -> None:
		if self.docstatus != 0 and frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Outgoing Mail."))

	def validate_domain(self) -> None:
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
		validate_mailbox_for_outgoing(self.sender)

	def validate_amended_doc(self) -> None:
		if self.amended_from:
			frappe.throw(_("Amending {0} is not allowed.").format(frappe.bold("Outgoing Mail")))

	def validate_recipients(self) -> None:
		max_recipients = frappe.db.get_single_value(
			"Mail Settings", "max_recipients", cache=True
		)

		if len(self.recipients) > max_recipients:
			frappe.throw(
				_("Recipient limit exceeded ({0}). Maximum {0} recipients allowed.").format(
					frappe.bold(len(self.recipients)), frappe.bold(max_recipients)
				)
			)

		recipients = []
		for recipient in self.recipients:
			if recipient.recipient not in recipients:
				recipients.append(recipient.recipient)
			else:
				frappe.throw(
					_("Row #{0}: Duplicate recipient {1}.").format(
						recipient.idx, frappe.bold(recipient.recipient)
					)
				)

	def validate_body_html(self) -> None:
		if not self.body_html:
			self.body_html = ""

	def load_attachments(self) -> None:
		self.attachments = frappe.db.get_all(
			"File",
			fields=["name", "file_name", "file_url", "is_private", "file_size"],
			filters={"attached_to_doctype": self.doctype, "attached_to_name": self.name},
		)

		for attachment in self.attachments:
			attachment.type = "attachment"

	def validate_attachments(self) -> None:
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

	def set_from_ip(self) -> None:
		self.from_ip = frappe.local.request_ip

	def set_agent(self) -> None:
		if not self.agent:
			self.agent = get_outgoing_agent()

	def validate_use_raw_html(self) -> None:
		if self.use_raw_html:
			self.body_html = self.raw_html

		self.raw_html = ""

	def set_body_plain(self) -> None:
		self.body_plain = html2text(self.body_html)

	def set_message_id(self) -> None:
		self.message_id = make_msgid(domain=self.domain_name)

	def set_tracking_id(self) -> None:
		self.tracking_id = uuid4().hex

	def set_original_message(self) -> None:
		def _get_message() -> "MIMEMultipart":
			message = MIMEMultipart("alternative")
			display_name = frappe.get_cached_value("Mailbox", self.sender, "display_name")
			message["From"] = (
				"{0} <{1}>".format(display_name, self.sender) if display_name else self.sender
			)
			message["To"] = self._get_recipients()
			message["Subject"] = self.subject
			message["Date"] = formatdate(localtime=True)
			message["Message-ID"] = self.message_id

			body_html = self._replace_image_url_with_content_id()
			body_plain = html2text(body_html)
			body_html = add_tracking_pixel(body_html, self.tracking_id)

			message.attach(MIMEText(body_plain, "plain", "utf-8"))
			message.attach(MIMEText(body_html, "html", "utf-8"))

			return message

		def _add_custom_headers(message: "MIMEMultipart") -> None:
			if self.custom_headers:
				for header in self.custom_headers:
					message.add_header(header.key, header.value)

		def _add_attachments(message: "MIMEMultipart") -> None:
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
		for recipient in self.recipients:
			if not frappe.db.exists("Mail Contact", recipient.recipient):
				mail_contact = frappe.new_doc("Mail Contact")
				mail_contact.user = frappe.session.user
				mail_contact.email = recipient.recipient
				mail_contact.display_name = recipient.display_name
				mail_contact.save()

	def send_mail(self) -> None:
		request_data = {
			"outgoing_mail": self.name,
			"message": self.original_message,
		}
		self._db_set(status="Queued", notify_update=True)
		create_agent_job(self.agent, "Send Mail", request_data=request_data)

	def _get_recipients(self, as_list: bool = False) -> str | list[str]:
		recipients = [
			f"{r.display_name} <{r.recipient}>" if r.display_name else r.recipient
			for r in self.recipients
		]
		return recipients if as_list else ", ".join(recipients)

	def _replace_image_url_with_content_id(self) -> str:
		body_html = self.body_html or ""

		if body_html and self.attachments:
			img_src_pattern = r'<img.*?src="(.*?)".*?>'

			for img_src_match in finditer(img_src_pattern, body_html):
				img_src = img_src_match.group(1)

				if content_id := self._get_attachment_content_id(img_src, set_as_inline=True):
					body_html = body_html.replace(img_src, f"cid:{content_id}")

		return body_html

	def _get_attachment_content_id(
		self, file_url: str, set_as_inline: bool = False
	) -> Optional[str]:
		for attachment in self.attachments:
			if file_url in attachment.file_url:
				if set_as_inline:
					attachment.type = "inline"

				return attachment.name

	def _get_attachment_file_url(self, content_id: str) -> Optional[str]:
		for attachment in self.attachments:
			if content_id == attachment.name:
				return attachment.file_url

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify_update: bool = False,
		**kwargs,
	) -> None:
		self.db_set(kwargs, update_modified=update_modified, commit=commit)

		if notify_update:
			self.notify_update()

	@frappe.whitelist()
	def retry_send_mail(self) -> None:
		if self.docstatus == 1 and self.status == "Failed":
			self._db_set(error_log=None)
			self.send_mail()


def add_tracking_pixel(body_html: str, tracking_id: str) -> str:
	soup = BeautifulSoup(body_html, "html.parser")
	src = (
		f"{frappe.utils.get_url()}/api/method/mail.api.track_open?tracking_id={tracking_id}"
	)
	tracking_pixel = soup.new_tag(
		"img", src=src, width="1", height="1", style="display:none;"
	)

	if not soup.body:
		body_html = f"<html><body>{body_html}</body></html>"
		soup = BeautifulSoup(body_html, "html.parser")

	soup.body.insert(0, tracking_pixel)
	return str(soup)


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
	MAILBOX = frappe.qb.DocType("Mailbox")
	DOMAIN = frappe.qb.DocType("Mail Domain")
	return (
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
		.limit(page_len)
	).run(as_dict=False)


def update_outgoing_mail_status(agent_job: "MailAgentJob") -> None:
	if agent_job and agent_job.job_type == "Send Mail":
		kwargs = {}

		if agent_job.status == "Running":
			kwargs.update({"status": "Transferring"})
			outgoing_mail = frappe.get_doc(
				"Outgoing Mail", json_loads(agent_job.request_data).get("outgoing_mail")
			)
			outgoing_mail._db_set(**kwargs, commit=True)
			return

		elif agent_job.status == "Failed":
			kwargs.update({"status": "Failed", "error_log": agent_job.error_log})

		elif agent_job.status == "Completed":
			kwargs.update({"status": "Transferred", "transferred_at": now()})

		if kwargs:
			outgoing_mail = frappe.get_doc(
				"Outgoing Mail", json_loads(agent_job.request_data)["outgoing_mail"]
			)

			if kwargs.get("status") == "Transferred":
				kwargs["transferred_after"] = time_diff_in_seconds(
					kwargs["transferred_at"], outgoing_mail.created_at
				)

			outgoing_mail._db_set(**kwargs, notify_update=True)


@frappe.whitelist()
def get_delivery_status(agents: Optional[str | list] = None) -> None:
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
				& (OM.status == "Transferred")
			)
		).run(pluck="name")

	elif isinstance(agents, str):
		agents = [agents]

	for agent in agents:
		create_agent_job(agent, "Get Delivery Status")


def update_outgoing_mails_delivery_status(agent_job: "MailAgentJob") -> None:
	def _validate_data(data: dict) -> None:
		if data:
			fields = ["message_id", "outgoing_mail", "status", "recipients"]

			for field in fields:
				if not data.get(field):
					frappe.throw(_("{0} is required.").format(frappe.bold(field)))
		else:
			frappe.throw(_("Invalid Request Data."))

	if agent_job and agent_job.job_type == "Get Delivery Status":
		if agent_job.status == "Completed":
			if data := json_loads(agent_job.response_data)["message"]:
				for d in data:
					_validate_data(d)

					if outgoing_mail := frappe.get_doc(
						"Outgoing Mail",
						{"name": d.get("outgoing_mail"), "message_id": d.get("message_id")},
					):
						for recipient in outgoing_mail.recipients:
							recipient.sent = d["recipients"][recipient.recipient]["sent"]

							if recipient.sent:
								recipient.sent_at = d["recipients"][recipient.recipient]["sent_at"]
								recipient.sent_after = time_diff_in_seconds(
									recipient.sent_at, outgoing_mail.created_at
								)
							else:
								recipient.bounce_at = d["recipients"][recipient.recipient]["bounce_at"]
								recipient.bounce_after = time_diff_in_seconds(
									recipient.bounce_at, outgoing_mail.created_at
								)

							recipient.details = d["recipients"][recipient.recipient]["details"]
							recipient.db_update()

						outgoing_mail._db_set(status=d["status"], notify_update=True)
