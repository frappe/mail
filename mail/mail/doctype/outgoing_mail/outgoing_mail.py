# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from uuid import uuid4
from re import finditer
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
from frappe.desk.form.load import get_attachments
from frappe.utils.password import get_decrypted_password
from mail.utils import get_outgoing_server, parsedate_to_datetime
from frappe.utils import now, get_datetime_str, time_diff_in_seconds
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job


if TYPE_CHECKING:
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class OutgoingMail(Document):
	def validate(self) -> None:
		self.validate_domain()
		self.validate_sender()
		self.validate_amended_doc()
		self.validate_recipients()
		self.validate_body_html()

		if self.get("_action") == "submit":
			self.set_from_ip()
			self.set_server()
			self.validate_use_raw_html()
			self.set_attachments()
			self.set_body_plain()
			self.set_message_id()
			self.set_token()
			self.set_original_message()

	def on_submit(self) -> None:
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
		enabled, status, mailbox_type = frappe.db.get_value(
			"Mailbox", self.sender, ["enabled", "status", "mailbox_type"]
		)

		if not enabled:
			frappe.throw(_("Mailbox {0} is disabled.").format(frappe.bold(self.sender)))
		elif status != "Active":
			frappe.throw(_("Mailbox {0} is not active.").format(frappe.bold(self.sender)))
		elif mailbox_type not in ["Outgoing", "Incoming and Outgoing"]:
			frappe.throw(
				_("Mailbox {0} is not allowed for Outgoing Mail.").format(frappe.bold(self.sender))
			)

	def validate_amended_doc(self) -> None:
		if self.amended_from:
			frappe.throw(_("Amending {0} is not allowed.").format(frappe.bold("Outgoing Mail")))

	def validate_recipients(self) -> None:
		recipient_limit = frappe.db.get_single_value(
			"Mail Settings", "recipient_limit", cache=True
		)

		if len(self.recipients) > recipient_limit:
			frappe.throw(
				"Recipient limit exceeded. Maximum {0} recipients allowed.".format(
					frappe.bold(recipient_limit)
				)
			)

		recipients = []
		for recipient in self.recipients:
			if recipient.recipient not in recipients:
				recipients.append(recipient.recipient)
			else:
				frappe.throw(
					"Row #{0}: Duplicate recipient {1}.".format(
						recipient.idx, frappe.bold(recipient.recipient)
					)
				)

	def validate_body_html(self) -> None:
		if not self.body_html:
			self.body_html = ""

	def set_from_ip(self) -> None:
		self.from_ip = frappe.local.request_ip

	def set_server(self) -> None:
		if not self.server:
			self.server = get_outgoing_server()

	def validate_use_raw_html(self) -> None:
		if self.use_raw_html:
			self.body_html = self.raw_html

		self.raw_html = ""

	def set_attachments(self) -> None:
		self.attachments = get_attachments(self.doctype, self.name)
		for attachment in self.attachments:
			attachment.type = "attachment"

	def set_body_plain(self) -> None:
		self.body_plain = html2text(self.body_html)

	def set_message_id(self) -> None:
		self.message_id = make_msgid(domain=self.domain_name)

	def set_token(self) -> None:
		self.token = uuid4().hex

	def set_original_message(self) -> None:
		def __get_message() -> "MIMEMultipart":
			message = MIMEMultipart("alternative")
			display_name = frappe.get_cached_value("Mailbox", self.sender, "display_name")
			message["From"] = (
				"{0} <{1}>".format(display_name, self.sender) if display_name else self.sender
			)
			message["To"] = self.get_recipients()
			message["Subject"] = self.subject
			message["Date"] = formatdate(localtime=True)
			message["Message-ID"] = self.message_id

			body_html = self._replace_image_url_with_content_id()
			body_plain = html2text(body_html)

			message.attach(MIMEText(body_plain, "plain", "utf-8"))
			message.attach(MIMEText(body_html, "html", "utf-8"))

			return message

		def __add_custom_headers(message: "MIMEMultipart") -> None:
			if self.custom_headers:
				for header in self.custom_headers:
					message.add_header(header.key, header.value)

		def __add_attachments(message: "MIMEMultipart") -> None:
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

		def __add_dkim_signature(message: "MIMEMultipart") -> None:
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

		message = __get_message()
		__add_custom_headers(message)
		__add_attachments(message)
		__add_dkim_signature(message)

		self.original_message = message.as_string()
		self.created_at = get_datetime_str(parsedate_to_datetime(message["Date"]))

	def send_mail(self) -> None:
		request_data = {
			"outgoing_mail": self.name,
			"message": self.original_message,
		}
		self._db_set(status="Queued", notify_update=True)
		create_agent_job(self.server, "Send Mail", request_data=request_data)

	def get_recipients(self, as_list: bool = False) -> str | list[str]:
		recipients = [d.recipient for d in self.recipients]
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
	return (
		frappe.qb.from_(MAILBOX)
		.select(MAILBOX.name)
		.where(
			(MAILBOX.enabled == 1)
			& (MAILBOX.status == "Active")
			& (MAILBOX[searchfield].like(f"%{txt}%"))
			& (MAILBOX.mailbox_type.isin(["Outgoing", "Incoming and Outgoing"]))
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
def get_delivery_status(servers: Optional[str | list] = None) -> None:
	if not servers:
		MS = frappe.qb.DocType("Mail Server")
		OM = frappe.qb.DocType("Outgoing Mail")
		servers = (
			frappe.qb.from_(MS)
			.left_join(OM)
			.on(OM.server == MS.name)
			.select(MS.name)
			.distinct()
			.where(
				(MS.enabled == 1)
				& (MS.outgoing == 1)
				& (OM.docstatus == 1)
				& (OM.status == "Transferred")
			)
		).run(pluck="name")

	elif isinstance(servers, str):
		servers = [servers]

	for server in servers:
		create_agent_job(server, "Get Delivery Status")


def update_outgoing_mails_delivery_status(agent_job: "MailAgentJob") -> None:
	def __validate_data(data: dict) -> None:
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
					__validate_data(d)

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

							recipient.description = d["recipients"][recipient.recipient]["description"]
							recipient.db_update()

						outgoing_mail._db_set(status=d["status"], notify_update=True)
