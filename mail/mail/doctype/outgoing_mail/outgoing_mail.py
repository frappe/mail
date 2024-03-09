# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import dkim
import json
import frappe
import string
import secrets
from frappe import _
from datetime import datetime
from email.utils import formatdate
from email.mime.text import MIMEText
from frappe.core.utils import html2text
from typing import TYPE_CHECKING, Optional
from mail.utils import get_outgoing_server
from frappe.model.document import Document
from email.mime.multipart import MIMEMultipart
from frappe.utils.password import get_decrypted_password
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job

if TYPE_CHECKING:
	from mail.mail.doctype.mail_agent_job.mail_agent_job import MailAgentJob


class OutgoingMail(Document):
	def validate(self) -> None:
		self.validate_amended_doc()
		self.validate_recipients()
		self.validate_body_html()

		if self.get("_action") == "submit":
			self.set_from_ip()
			self.validate_server()
			self.set_body_plain()
			self.set_message_id()
			self.set_original_message()

	def on_submit(self) -> None:
		self.sendmail()

	def on_trash(self) -> None:
		if self.docstatus != 0 and frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Outgoing Mail."))

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
		message["Date"] = formatdate()
		message["Message-ID"] = self.message_id

		if self.custom_headers:
			for header in self.custom_headers:
				message.add_header(header.key, header.value)

		if self.body_html:
			message.attach(MIMEText(self.body_html, "html"))

		if self.body_plain:
			message.attach(MIMEText(self.body_plain, "plain"))

		headers = [b"To", b"From", b"Subject"]
		signature = dkim.sign(
			message=message.as_bytes(),
			domain=self.domain_name.encode(),
			selector=dkim_selector.encode(),
			privkey=dkim_private_key.encode(),
			include_headers=headers,
		)
		message["DKIM-Signature"] = signature[len("DKIM-Signature: ") :].decode()

		return message.as_string()

	def sendmail(self) -> None:
		request_data = {
			"outgoing_mail": self.name,
			"message": self.original_message,
			"callback_url": get_callback_url(),
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
	def resend(self) -> None:
		if self.docstatus == 1:
			self._db_set(error_log=None)
			self.sendmail()


def get_callback_url() -> str:
	return f"{frappe.utils.get_url()}/api/method/mail.mail.doctype.outgoing_mail.outgoing_mail.update_delivery_status"


@frappe.whitelist(allow_guest=True)
def update_delivery_status(agent_job: Optional["MailAgentJob"] = None) -> None:
	def validate_request_data(data: dict) -> None:
		if data:
			fields = ["message_id", "token", "status", "recipients"]

			for field in fields:
				if not data.get(field):
					frappe.throw(_("{0} is required.").format(frappe.bold(field)))
		else:
			frappe.throw(_("Invalid Request Data."))

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
			if response_data := json.loads(agent_job.response_data)["message"]:
				kwargs.update({"status": "Transferred", "token": response_data["token"]})

		if kwargs:
			outgoing_mail = frappe.get_doc(
				"Outgoing Mail", json.loads(agent_job.request_data)["outgoing_mail"]
			)
			outgoing_mail._db_set(**kwargs, notify_update=True)

	else:
		frappe.set_user("daemon@frappemail.com")
		data = json.loads(frappe.request.data.decode())

		for d in data:
			validate_request_data(d)
			if outgoing_mail := frappe.get_doc(
				"Outgoing Mail", {"message_id": d.get("message_id"), "token": d.get("token")}
			):
				outgoing_mail.status = d["status"]

				for recipient in outgoing_mail.recipients:
					recipient.sent = d["recipients"][recipient.recipient]["sent"]
					recipient.description = d["recipients"][recipient.recipient]["description"]
					recipient.db_update()

				outgoing_mail.db_update()
