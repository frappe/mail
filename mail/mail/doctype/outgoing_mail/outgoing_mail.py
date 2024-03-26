# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import dkim
import json
import frappe
import string
import secrets
from frappe import _
from uuid import uuid4
from typing import Optional
from datetime import datetime
from typing import TYPE_CHECKING
from email.utils import formatdate
from email.mime.text import MIMEText
from frappe.core.utils import html2text
from frappe.utils import get_datetime_str
from frappe.model.document import Document
from email.mime.multipart import MIMEMultipart
from frappe.utils.password import get_decrypted_password
from mail.utils import get_outgoing_server, parsedate_to_datetime
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
			self.validate_server()
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

	def validate_server(self) -> None:
		if not self.server:
			self.server = get_outgoing_server()

	def set_body_plain(self) -> None:
		self.body_plain = html2text(self.body_html)

	def set_message_id(self) -> None:
		self.message_id = "<{0}.{1}@{2}>".format(
			datetime.now().strftime("%Y%m%d%H%M%S"),
			"".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(11)),
			self.domain_name,
		)

	def set_token(self) -> None:
		self.token = uuid4().hex

	def set_original_message(self) -> None:
		self.original_message = self.get_signed_message()

	def get_signed_message(self) -> str:
		display_name = frappe.get_cached_value("Mailbox", self.sender, "display_name")
		dkim_selector = frappe.get_cached_value(
			"Mail Domain", self.domain_name, "dkim_selector"
		)
		dkim_private_key = get_decrypted_password(
			"Mail Domain", self.domain_name, "dkim_private_key"
		)

		message = MIMEMultipart("alternative")
		message["From"] = (
			"{0} <{1}>".format(display_name, self.sender) if display_name else self.sender
		)
		message["To"] = ", ".join(self.get_recipients())
		message["Subject"] = self.subject
		message["Date"] = formatdate(localtime=True)
		message["Message-ID"] = self.message_id

		if self.custom_headers:
			for header in self.custom_headers:
				message.add_header(header.key, header.value)

		if self.body_plain:
			message.attach(MIMEText(self.body_plain, "plain"))

		if self.body_html:
			message.attach(MIMEText(self.body_html, "html"))

		headers = [b"To", b"From", b"Subject"]
		signature = dkim.sign(
			message=message.as_bytes(),
			domain=self.domain_name.encode(),
			selector=dkim_selector.encode(),
			privkey=dkim_private_key.encode(),
			include_headers=headers,
		)
		message["DKIM-Signature"] = signature[len("DKIM-Signature: ") :].decode()
		self.created_at = get_datetime_str(parsedate_to_datetime(message["Date"]))

		return message.as_string()

	def send_mail(self) -> None:
		request_data = {
			"outgoing_mail": self.name,
			"message": self.original_message,
		}
		self._db_set(status="Queued", notify_update=True)
		create_agent_job(self.server, "Send Mail", request_data=request_data)

	def get_recipients(self) -> None:
		return [d.recipient for d in self.recipients]

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
				"Outgoing Mail", json.loads(agent_job.request_data).get("outgoing_mail")
			)
			outgoing_mail._db_set(**kwargs, commit=True)
			return

		elif agent_job.status == "Failed":
			kwargs.update({"status": "Failed", "error_log": agent_job.error_log})

		elif agent_job.status == "Completed":
			kwargs.update({"status": "Transferred"})

		if kwargs:
			outgoing_mail = frappe.get_doc(
				"Outgoing Mail", json.loads(agent_job.request_data)["outgoing_mail"]
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
			if data := json.loads(agent_job.response_data)["message"]:
				for d in data:
					__validate_data(d)

					if outgoing_mail := frappe.get_doc(
						"Outgoing Mail",
						{"name": d.get("outgoing_mail"), "message_id": d.get("message_id")},
					):
						outgoing_mail.status = d["status"]
						for recipient in outgoing_mail.recipients:
							recipient.sent = d["recipients"][recipient.recipient]["sent"]
							recipient.sent_at = d["recipients"][recipient.recipient]["sent_at"]
							recipient.description = d["recipients"][recipient.recipient]["description"]
							recipient.db_update()

						outgoing_mail.db_update()
