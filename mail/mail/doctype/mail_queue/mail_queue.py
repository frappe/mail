# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from email import message_from_string
from email.utils import make_msgid, parseaddr
from mimetypes import guess_type
from pathlib import Path
from typing import Any, Literal

import frappe
from frappe import _
from frappe.core.doctype.file.file import File
from frappe.core.doctype.file.file import has_permission as has_file_permission
from frappe.core.doctype.file.utils import find_file_by_url
from frappe.model.document import Document
from frappe.query_builder import Case, Order
from frappe.utils import (
	add_to_date,
	cint,
	create_batch,
	get_datetime,
	get_datetime_str,
	now,
	now_datetime,
	random_string,
	time_diff_in_seconds,
)
from uuid_utils import uuid7

from mail import __version__
from mail.jmap import get_identities, get_jmap_client, get_mailbox_id_by_role
from mail.utils.cache import get_account_for_email, get_account_for_user
from mail.utils.dt import convert_to_utc, parsedate_to_datetime
from mail.utils.user import get_account_email_addresses, is_account_owner, is_system_manager
from mail.utils.validation import validate_domain_is_enabled_and_verified, validate_email_address


class MailQueue(Document):
	@staticmethod
	def clear_old_logs(days: int = 3) -> None:
		MQ = frappe.qb.DocType("Mail Queue")
		(
			frappe.qb.from_(MQ)
			.where(
				(MQ.status.isin(["Drafted", "Submitted"]))
				& (MQ.creation < get_datetime(add_to_date(now(), days=-days)))
			)
			.delete()
		).run()

	@staticmethod
	def _get_file(
		name: str | None = None,
		file_url: str | None = None,
		user: str | None = None,
		check_permission: bool = True,
	) -> File:
		"""Returns the File document for the given name or file URL."""

		if not name and not file_url:
			frappe.throw(_("Either name or file URL is required."))

		file = None
		if name:
			file = frappe.get_doc("File", name)
		elif file_url:
			file = find_file_by_url(file_url)

		if not file:
			frappe.throw(_("File <code>{0}</code> not found.").format(name or file_url))

		if check_permission:
			if not has_file_permission(file, "read", user=user):
				frappe.throw(
					_("User {0} do not have permission to access the file <code>{1}</code>.").format(
						frappe.bold(user or frappe.session.user), name or file_url
					)
				)

		return file

	@staticmethod
	def _create(do_not_save: bool = False, **kwargs) -> "MailQueue":
		"""Create a new MailQueue document."""

		kwargs = frappe._dict(kwargs)

		doc = frappe.new_doc("Mail Queue")
		doc.account = kwargs.account
		doc.from_name = kwargs.from_name
		doc.from_email = kwargs.from_email
		doc.subject = kwargs.subject

		for field in ["reply_to", "headers", "recipients", "attachments"]:
			if kwargs.get(field):
				setattr(doc, field, json.dumps(kwargs[field]))

		doc.html_body = kwargs.html_body
		doc.text_body = kwargs.text_body
		doc.forwarded_from_id = kwargs.forwarded_from_id
		doc.message_id = kwargs.message_id
		doc._id = kwargs._id
		doc.via_api = cint(kwargs.via_api)
		doc.newsletter = cint(kwargs.newsletter)
		doc.sent_at = kwargs.sent_at
		doc.in_reply_to = kwargs.in_reply_to
		doc.in_reply_to_id = kwargs.in_reply_to_id
		doc.save_as_draft = cint(kwargs.save_as_draft)
		doc.destroy_after_submission = cint(kwargs.destroy_after_submission)
		doc.delivery_mode = kwargs.delivery_mode or "Immediate"
		doc.raw_message = kwargs.raw_message

		if not do_not_save:
			if frappe.flags.read_only:
				if not doc.name:
					doc.set_new_name()

				doc.delivery_mode = "Immediate"
				doc.validate()
				doc._process()

				if doc.status in ["Failed", "Failed to Draft", "Failed to Submit"]:
					error_message = doc.error_message or "Request Failed"
					frappe.throw(error_message)
			else:
				doc.insert()

		return doc

	@property
	def _priority(self) -> str:
		"""Returns the MT-Priority value based on the priority field."""

		mt_priority_map = {
			"Low": "-4",
			"Normal": "0",
			"High": "4",
		}
		return mt_priority_map.get(self.priority, "0")

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
	def received_after(self) -> float:
		"""Returns the time difference in seconds between creation and sent time."""

		if self.sent_at and self.creation:
			time_diff = time_diff_in_seconds(self.creation, self.sent_at)
			if time_diff > 0:
				return time_diff

		return 0.0

	@property
	def queued_after(self) -> float:
		"""Returns the time difference in seconds between queued and creation time."""

		return time_diff_in_seconds(self.queued_at, self.creation) if self.queued_at else 0.0

	@property
	def drafted_after(self) -> float:
		"""Returns the time difference in seconds between drafted and creation time."""

		return time_diff_in_seconds(self.drafted_at, self.creation) if self.drafted_at else 0.0

	@property
	def submitted_after(self) -> float:
		"""Returns the time difference in seconds between submitted and creation time."""

		return time_diff_in_seconds(self.submitted_at, self.creation) if self.submitted_at else 0.0

	@property
	def identity_id(self) -> str:
		"""Returns the identity ID for the from email."""

		for identity in get_identities(self.account):
			if identity["email"] == self.from_email:
				return identity["id"]

		frappe.throw(_("Identity not found for email {0}").format(self.from_email))

	@property
	def message(self) -> str | None:
		"""Returns the message content if available."""

		from mail.mail.doctype.mail_message.mail_message import _get_blob_cache_key

		cache_key = _get_blob_cache_key(self.account, self.blob_id)
		if content := frappe.cache.get_value(cache_key):
			return content.decode("utf-8")

	@property
	def response(self) -> str | None:
		"""Returns the indented JSON response."""

		_response = json_loads(self._response)
		return json.dumps(_response, indent=4) if _response else None

	@property
	def error_message(self) -> str | None:
		"""Returns the error message."""

		if not self._response or self.status not in ["Failed to Draft", "Failed to Submit"]:
			return None

		response = json_loads(self._response)

		data = None
		if self.status == "Failed to Draft":
			data = response["methodResponses"][0][1].get("notCreated", {}).get(f"draft-{self.name}")
		elif self.status == "Failed to Submit":
			data = response["methodResponses"][-1][1].get("notCreated", {}).get(f"submit-{self.name}")

		if data:
			message = f"{data['type']}: {data['description']}"

			if data.get("properties"):
				message += f" ({', '.join(data['properties'])})"

			return message

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		if self.is_new():
			self.validate_status()
			self.validate_account()
			self.validate_raw_message()
			self.validate_from_name()
			self.validate_from_email()
			self.validate_destroy_after_submission()
			self.validate_delivery_mode()
			self.validate_reply_to()
			self.validate_headers()
			self.validate_recipients()
			self.validate_attachments()
			self.validate_message_id()
			self.validate_from_ip()
			self.validate_sent_at()
			self.validate_priority()
			self.validate_in_reply_to()
			self.validate_in_reply_to_id()

	def after_insert(self) -> None:
		if self.delivery_mode == "Immediate":
			self._process()
		elif self.delivery_mode == "Enqueue":
			frappe.enqueue_doc(self.doctype, self.name, "_process", queue="short", enqueue_after_commit=True)

	def validate_status(self) -> None:
		"""Validates the status."""

		if self.delivery_mode == "Immediate":
			self.status = None
			self.queued_at = None
		elif self.delivery_mode == "Enqueue":
			self.status = "Queued"
			self.queued_at = now()
		elif self.delivery_mode == "Batch":
			self.status = "Pending"
			self.queued_at = None

	def validate_account(self) -> None:
		"""Validates the account."""

		if not self.account:
			frappe.throw(_("Account is required."))

		enabled, domain_name = frappe.db.get_value("Mail Account", self.account, ["enabled", "domain_name"])
		if not enabled:
			frappe.throw(_("Mail account {0} is disabled.").format(frappe.bold(self.account)))

		validate_domain_is_enabled_and_verified(domain_name)

	def validate_raw_message(self) -> None:
		"""Validates the raw message."""

		if not self.raw_message:
			return

		self.from_name = None
		self.from_email = None
		self.subject = None
		self.reply_to = None
		self.headers = None
		self.html_body = None
		self.text_body = None
		self.attachments = None
		self.message_id = None
		self.sent_at = None
		self.in_reply_to = None

		message = message_from_string(self.raw_message)
		if from_header := message.get("From"):
			self.from_name, self.from_email = parseaddr(from_header)

			if self.from_email not in get_account_email_addresses(self.account):
				# If the `From` address doesn't match any of the account's associated addresses,
				# reset it to fall back to the account's default email address.
				self.from_email = None

		if message_id := message.get("Message-ID"):
			self.message_id = message_id.strip("<>")

		if not json_loads(self.recipients):
			recipients = []
			for rcpt_type in ["To", "Cc", "Bcc"]:
				if _rcpt := message.get(rcpt_type):
					for rcpt in _rcpt.split(","):
						recipients.append(
							{
								"type": rcpt_type,
								"display_name": parseaddr(rcpt)[0],
								"email": parseaddr(rcpt)[1],
							}
						)

			self.recipients = json.dumps(recipients)

		if date_header := message.get("Date"):
			self.sent_at = get_datetime_str(parsedate_to_datetime(date_header))
		if in_reply_to := message.get("In-Reply-To"):
			self.in_reply_to = in_reply_to.strip("<>")

	def validate_from_name(self) -> None:
		"""Validates the from name."""

		if self.raw_message:
			return

		display_name, override_display_name = frappe.db.get_value(
			"Mail Account", self.account, ["display_name", "override_display_name"]
		)
		if not self.from_name or override_display_name:
			self.from_name = display_name

	def validate_from_email(self) -> None:
		"""Validates the from email."""

		if self.from_email:
			if self.account != get_account_for_email(self.from_email):
				frappe.throw(
					_(
						"You cannot send email from {0} using account {1}. Please use the email address associated with the account."
					).format(frappe.bold(self.from_email), frappe.bold(self.account))
				)
		else:
			self.from_email = frappe.db.get_value("Mail Account", self.account, "default_outgoing_email")

	def validate_destroy_after_submission(self) -> None:
		"""Validates the destroy after submission setting."""

		if self.save_as_draft or self.destroy_after_submission:
			return

		if self.newsletter:
			if frappe.db.get_value("Mail Account", self.account, "destroy_newsletter_after_submission"):
				self.destroy_after_submission = 1
		elif frappe.db.get_value("Mail Account", self.account, "destroy_email_after_submission"):
			self.destroy_after_submission = 1

	def validate_delivery_mode(self) -> None:
		"""Validates the delivery mode."""

		if self.delivery_mode:
			if self.delivery_mode not in ["Immediate", "Enqueue", "Batch"]:
				frappe.throw(_("Invalid delivery mode: {0}").format(self.delivery_mode))
		else:
			self.delivery_mode = "Immediate"

	def validate_reply_to(self) -> None:
		"""Validates the reply to."""

		if self.raw_message:
			return

		default_reply_to, override_reply_to = frappe.db.get_value(
			"Mail Account", self.account, ["reply_to", "override_reply_to"]
		)

		reply_to = []
		if not override_reply_to:
			for rt in json_loads(self.reply_to, default=[]):
				reply_to.append(
					{
						"display_name": rt.get("display_name"),
						"email": rt["email"],
					}
				)

		if not reply_to and default_reply_to:
			for rt in default_reply_to.split(","):
				display_name, email = parseaddr(rt)
				if email:
					reply_to.append(
						{
							"display_name": display_name,
							"email": email,
						}
					)

		self.reply_to = json.dumps(reply_to)

	def validate_headers(self) -> None:
		"""Validates the headers."""

		standard_headers = {
			"from",
			"to",
			"cc",
			"bcc",
			"subject",
			"date",
			"message-id",
			"in-reply-to",
			"references",
			"reply-to",
			"user-agent",
			"sender",
			"return-path",
			"mime-version",
			"content-type",
			"content-transfer-encoding",
			"content-language",
			"x-mailer",
			"x-priority",
			"x-mail-queue",
		}

		headers = {}
		for key, value in json_loads(self.headers, default={}).items():
			if key.lower() in standard_headers:
				frappe.throw(
					_(
						"The header <b>{0}</b> is a standard email header and cannot be overridden. Please use custom headers prefixed with <code>X-</code>."
					).format(key)
				)

			headers[key] = value

		self.headers = json.dumps(headers)

	def validate_recipients(self) -> None:
		"""Validates the recipients."""

		recipients = []
		for rcpt in json_loads(self.recipients, default=[]):
			if not rcpt["type"] or not rcpt["email"]:
				continue

			if not validate_email_address(rcpt["email"], check_mx=False, verify=False):
				frappe.throw(_("Invalid email address: {0}").format(frappe.bold(rcpt["email"])))

			recipients.append(
				{
					"type": rcpt["type"],
					"display_name": rcpt.get("display_name"),
					"email": rcpt["email"],
				}
			)

		if not recipients and not self.save_as_draft:
			frappe.throw(_("Please add at least one recipient."))

		self.recipients = json.dumps(recipients)

	def validate_attachments(self) -> None:
		"""Validates the attachments."""

		user = frappe.session.user
		if user == "Administrator":
			user = frappe.db.get_value("Mail Account", self.account, "user")

		blob_ids = []
		attachments = []
		for a in json_loads(self.attachments, default=[]):
			if blob_id := a.get("blob_id"):
				if blob_id not in blob_ids:
					attachments.append(
						{
							"blob_id": blob_id,
							"type": a["type"],
							"size": a["size"],
							"filename": a["filename"],
							"disposition": a["disposition"],
							"cid": a["cid"]
							if a["disposition"] == "inline"
							else a.get("cid", random_string(length=10)),
						}
					)
					blob_ids.append(blob_id)
			elif file_url := a.get("file_url"):
				if file_url.startswith("/private/files"):
					MailQueue._get_file(file_url=file_url, user=user, check_permission=True)
				elif not file_url.startswith("/files"):
					frappe.throw(
						_(
							"Invalid file URL: {0}. File URLs must start with '/files/' or '/private/files/'."
						).format(file_url)
					)

				attachments.append(
					{
						"file_url": file_url,
						"filename": a.get("filename") or Path(file_url).name,
						"disposition": a["disposition"],
						"cid": a["cid"]
						if a["disposition"] == "inline"
						else a.get("cid", random_string(length=10)),
					}
				)
			else:
				frappe.throw(_("Either blob_id or file_url is required for attachments."))

		self.attachments = json.dumps(attachments)

	def validate_message_id(self) -> None:
		"""Validates the message ID."""

		if not self.message_id:
			self.message_id = make_msgid(domain=self.from_email.split("@")[-1]).strip("<>")

	def validate_from_ip(self) -> None:
		"""Validates the from IP address."""

		self.from_ip = frappe.local.request_ip

	def validate_sent_at(self) -> None:
		"""Validates the sent at date."""

		if not self.raw_message:
			self.sent_at = now()

	def validate_priority(self) -> None:
		"""Validates the priority."""

		if self.priority:
			return

		if self.newsletter:
			self.priority = "Low"
		elif self.received_after <= 5:
			self.priority = "High"
		else:
			self.priority = "Normal"

	def validate_in_reply_to(self) -> None:
		"""Validates the In Reply To (Message ID)."""

		if self.in_reply_to:
			self.in_reply_to = self.in_reply_to.strip("<>")

	def validate_in_reply_to_id(self) -> None:
		"""Validates the In Reply To ID."""

		if self.in_reply_to and not self.in_reply_to_id:
			try:
				client = get_jmap_client(self.account)
				result = client.email_query({"header": ["Message-ID", self.in_reply_to]})
				if _ids := result["ids"]:
					self.in_reply_to_id = _ids[0]
			except Exception:
				self.in_reply_to_id = None
				frappe.log_error(_("Failed to fetch In Reply To ID"), frappe.get_traceback(with_context=True))

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retries Create, Update or Submit the Email."""

		frappe.only_for("System Manager")

		if self.status not in ["Failed", "Failed to Draft", "Failed to Submit"]:
			frappe.throw(_("Cannot retry a mail with status {0}").format(self.status))

		self._process()

	@frappe.whitelist()
	def get_mime_message(self) -> str:
		"""Returns the MIME message content."""

		if not self.blob_id:
			frappe.throw(_("Email does not have a blob ID."))

		from mail.mail.doctype.mail_message.mail_message import fetch_blob

		return fetch_blob(self.account, self.blob_id).decode("utf-8")

	def _process(self) -> None:
		"""Create, Update or Submit the Email."""

		kwargs = {}

		try:
			client = get_jmap_client(self.account)
			draft_mailbox_id = get_mailbox_id_by_role(self.account, role="drafts", raise_exception=True)
			sent_mailbox_id = get_mailbox_id_by_role(self.account, role="sent", raise_exception=True)

			using = ["urn:ietf:params:jmap:mail"]
			method_calls = []
			call_id = 0

			if self.raw_message:
				blob = client.upload_blob(self.raw_message.encode("utf-8"), content_type="message/rfc822")
				method_calls.append(
					[
						"Email/import",
						{
							"accountId": client.primary_account_id,
							"emails": {
								f"draft-{self.name}": {
									"blobId": blob["blobId"],
									"mailboxIds": {draft_mailbox_id: True},
									"keywords": {"$draft": True, "$seen": True},
								}
							},
						},
						str(call_id),
					]
				)
				call_id += 1

				if self._id:
					method_calls.append(
						[
							"Email/set",
							{
								"accountId": client.primary_account_id,
								"destroy": [self._id] if self._id else None,
							},
							str(call_id),
						]
					)
					call_id += 1
			else:
				attachments = []
				for a in json_loads(self.attachments, default=[]):
					blob_id = a.get("blob_id")
					if not blob_id:
						file = MailQueue._get_file(file_url=a["file_url"], check_permission=False)
						content = file.get_content()
						content_type = guess_type(file.file_name)[0]
						blob = client.upload_blob(content, content_type)
						a.update({"type": blob["type"], "size": blob["size"], "blob_id": blob["blobId"]})
					attachments.append(a)

				kwargs["attachments"] = json.dumps(attachments)
				method_calls.append(
					[
						"Email/set",
						{
							"accountId": client.primary_account_id,
							"create": {
								f"draft-{self.name}": self._draft_mail(
									draft_mailbox_id, attachments=attachments
								)
							},
							"destroy": [self._id] if self._id else None,
						},
						str(call_id),
					]
				)
				call_id += 1

			if not self.save_as_draft:
				recipients = list({rcpt["email"] for rcpt in json_loads(self.recipients)})
				submission_call = [
					"EmailSubmission/set",
					{
						"accountId": client.primary_account_id,
						"create": {
							f"submit-{self.name}": {
								"identityId": self.identity_id,
								"emailId": f"#draft-{self.name}",
								"envelope": {
									"mailFrom": {
										"email": self.from_email,
										"parameters": {
											"RET": "FULL",
											"ENVID": self.name,
											"MT-PRIORITY": self._priority,
										},
									},
									"rcptTo": [
										{
											"email": rcpt,
											"parameters": {
												"NOTIFY": "DELAY,FAILURE",
												"ORCPT": f"rfc822;{rcpt}",
											},
										}
										for rcpt in recipients
									],
								},
							}
						},
					},
					str(call_id),
				]

				updates = {}

				if self.destroy_after_submission:
					submission_call[1]["onSuccessDestroyEmail"] = [f"#submit-{self.name}"]
				else:
					updates[f"#submit-{self.name}"] = {
						f"mailboxIds/{draft_mailbox_id}": None,
						f"mailboxIds/{sent_mailbox_id}": True,
						"keywords/$draft": None,
						"keywords/$seen": True,
					}

				if self.forwarded_from_id or self.in_reply_to_id:
					for _id, keyword in [
						(self.forwarded_from_id, "$forwarded"),
						(self.in_reply_to_id, "$answered"),
					]:
						if not _id:
							continue

						updates.setdefault(_id, {}).update({f"keywords/{keyword}": True})

				if updates:
					submission_call[1]["onSuccessUpdateEmail"] = {
						_id: _updates for _id, _updates in updates.items()
					}

				using.append("urn:ietf:params:jmap:submission")
				method_calls.append(submission_call)
				call_id += 1

			response = client._make_request(using=using, method_calls=method_calls)

			kwargs.update({"status": "Failed", "_response": json.dumps(response)})
			if data := response["methodResponses"][0][1].get("created", {}).get(f"draft-{self.name}"):
				kwargs.update(
					{
						"status": "Drafted",
						"_id": data["id"],
						"blob_id": data["blobId"],
						"size": data["size"],
						"drafted_at": now(),
						"thread_id": data["threadId"],
						"mailbox_id": draft_mailbox_id,
					}
				)
			elif response["methodResponses"][0][1].get("notCreated", {}).get(f"draft-{self.name}"):
				retries = cint(self.retries) + 1
				kwargs.update(
					{
						"status": "Failed to Draft",
						"retries": retries,
						"next_retry_after": get_next_retry_after(retries),
					}
				)

			if not self.save_as_draft:
				idx = 2 if self.raw_message and self._id else 1
				if response["methodResponses"][idx][1].get("created", {}).get(f"submit-{self.name}"):
					kwargs.update(
						{
							"status": "Submitted",
							"submitted_at": now(),
							"mailbox_id": sent_mailbox_id,
						}
					)
				elif response["methodResponses"][idx][1].get("notCreated", {}).get(f"submit-{self.name}"):
					retries = cint(self.retries) + 1
					kwargs.update(
						{
							"status": "Failed to Submit",
							"retries": retries,
							"next_retry_after": get_next_retry_after(retries),
						}
					)
		except Exception:
			retries = cint(self.retries) + 1
			kwargs.update(
				{
					"status": "Failed",
					"retries": retries,
					"next_retry_after": get_next_retry_after(retries),
					"error_log": frappe.get_traceback(with_context=True),
				}
			)

		if frappe.flags.read_only:
			for key, value in kwargs.items():
				setattr(self, key, value)
		else:
			self._db_set(notify=True, **kwargs)

	def _draft_mail(self, draft_mailbox_id: str, attachments: list[dict] | None = None) -> dict:
		"""Returns the draft mail object."""

		mail = {
			"mailboxIds": {draft_mailbox_id: True},
			"keywords": {"$draft": True, "$seen": True},
			"from": [{"name": self.from_name, "email": self.from_email}],
		}

		for field in ["to", "cc", "bcc"]:
			if hasattr(self, field):
				if value := getattr(self, field):
					mail[field] = value

		if self.subject:
			mail["subject"] = self.subject

		mail.update(
			{
				"sentAt": convert_to_utc(self.sent_at).isoformat(),
				"header:Message-ID": f"<{self.message_id}>",
				"header:User-Agent": f"Frappe Mail v{__version__} (Frappe v{frappe.__version__})",
				"header:X-Mailer": "Frappe Mail",
			}
		)

		if reply_to := json_loads(self.reply_to):
			mail["header:Reply-To"] = ", ".join(
				[f'"{rt["display_name"]}" <{rt["email"]}>' for rt in reply_to]
			)

		if self.in_reply_to:
			mail["header:In-Reply-To"] = f"<{self.in_reply_to}>"

		mail["header:X-Mail-Queue"] = str(self.name)
		if headers := json_loads(self.headers):
			for key, value in headers.items():
				mail[f"header:{key}"] = str(value)

		mail["bodyValues"] = {}
		if self.text_body:
			mail["textBody"] = [{"partId": "text", "type": "text/plain"}]
			mail["bodyValues"]["text"] = {"value": self.text_body, "charset": "utf-8", "isTruncated": False}
		if self.html_body:
			mail["htmlBody"] = [{"partId": "html", "type": "text/html"}]
			mail["bodyValues"]["html"] = {"value": self.html_body, "charset": "utf-8", "isTruncated": False}

		_attachments = []
		for a in attachments or json_loads(self.attachments, default=[]):
			_attachments.append(
				{
					"name": a["filename"],
					"type": a["type"],
					"cid": a["cid"],
					"blobId": a["blob_id"],
					"disposition": a["disposition"],
				}
			)
		mail["attachments"] = _attachments

		return mail

	def _get_recipients(self, type: Literal["To", "Cc", "Bcc"] | None = None) -> list[dict[str, str | None]]:
		"""Returns the recipients."""

		recipients = []
		for rcpt in json_loads(self.recipients, default=[]):
			if type and rcpt["type"] != type:
				continue

			recipients.append({"name": rcpt["display_name"], "email": rcpt["email"]})

		return recipients

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


@frappe.whitelist()
def bulk_retry(names: str | list[str]) -> None:
	"""Retries the emails with the given names."""

	frappe.only_for("System Manager")

	if isinstance(names, str):
		names = json.loads(names)

	for name in names:
		doc = frappe.get_doc("Mail Queue", name)
		if doc.status in ["Failed", "Failed to Draft", "Failed to Submit"]:
			doc.retry()

	frappe.msgprint(
		_("Successfully retried {0} emails.").format(frappe.bold(len(names))),
		indicator="green",
		alert=True,
	)


def json_loads(data: str | None, default: Any = None) -> list | dict | None:
	"""Loads the given JSON data and returns it as a list or dict."""

	if data:
		return json.loads(data)

	return default


def get_next_retry_after(retries: int) -> str:
	"""Returns the next retry after datetime."""

	next_retry_after_minutes = retries * (retries + 1)  # 2, 6, 12, 20, 30 ...
	return add_to_date(now(), minutes=next_retry_after_minutes)


def process_pending_emails(mails: list[str]) -> None:
	"""Process pending emails."""

	failed_mails = []
	total_count = len(mails)

	for mail in mails:
		doc: "MailQueue" = frappe.get_doc("Mail Queue", mail)
		doc._process()

		if doc.status in ["Failed", "Failed to Draft", "Failed to Submit"]:
			failed_mails.append(mail)

			retries = len(failed_mails)
			failure_ratio = retries / total_count

			if failure_ratio > 0.33 and retries > 50:
				frappe.throw(
					_(
						"Email processing aborted: {retries} out of {total_count} emails failed "
						"({failure_rate:.2%} failure rate). Please investigate the issue before retrying."
					).format(retries=retries, total_count=total_count, failure_rate=failure_ratio)
				)


def enqueue_process_pending_emails(batch_size: int | None = None, max_batch_size: int | None = None) -> None:
	"""Enqueue process pending emails."""

	batch_size = batch_size or cint(frappe.conf.process_pending_emails_batch_size) or 2_500
	max_batch_size = max_batch_size or cint(frappe.conf.process_pending_emails_max_batch_size) or 25_000

	if batch_size > max_batch_size:
		batch_size = max_batch_size

	MQ = frappe.qb.DocType("Mail Queue")

	priority_order = Case()
	priority_order.when(MQ.priority == "High", 1)
	priority_order.when(MQ.priority == "Normal", 2)
	priority_order.when(MQ.priority == "Low", 3)
	priority_order.else_(4)

	mails = (
		frappe.qb.from_(MQ)
		.select(MQ.name)
		.where(
			(MQ.status == "Pending")
			| (
				(MQ.retries > 0)
				& (MQ.retries < MQ.max_retries)
				& (MQ.next_retry_after <= now_datetime())
				& (MQ.status.isin(["Failed", "Failed to Draft", "Failed to Submit"]))
			)
			| ((MQ.status == "Queued") & (MQ.queued_at <= get_datetime(add_to_date(now(), minutes=-30))))
		)
		.orderby(priority_order, MQ.creation, MQ.retries, order=Order.asc)
		.limit(max_batch_size)
	).run(pluck="name")

	if not mails:
		return

	try:
		(
			frappe.qb.update(MQ)
			.set(MQ.status, "Queued")
			.set(MQ.queued_at, now())
			.where((MQ.name.isin(mails)) & (MQ.status.notin(["Drafted", "Submitted"])))
		).run()

		for i, batch in enumerate(create_batch(mails, batch_size), start=1):
			frappe.enqueue(
				process_pending_emails,
				queue="long",
				timeout=cint(frappe.conf.process_pending_emails_timeout) or 1500,
				job_name=f"process_pending_emails_{i}_{len(batch)}",
				enqueue_after_commit=False,
				mails=batch,
			)

		# Recursively process next batch if the limit was reached.
		if len(mails) == max_batch_size:
			enqueue_process_pending_emails(batch_size, max_batch_size)

	except Exception:
		frappe.log_error(
			title="Failed - Enqueue Process Pending Emails", message=frappe.get_traceback(with_context=True)
		)


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	if account := get_account_for_user(user):
		return f"(`tabMail Queue`.account = '{account}')"
	else:
		return "1=0"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Queue":
		return False

	user = user or frappe.session.user
	user_is_system_manager = is_system_manager(user)
	user_is_account_owner = is_account_owner(doc.account, user)

	if user_is_system_manager or user_is_account_owner:
		return True

	return False
