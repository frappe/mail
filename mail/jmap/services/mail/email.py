from typing import ClassVar, Literal

import frappe

from mail import __version__
from mail.jmap.models import EmailCreateModel, EmailRecipient
from mail.jmap.services.core import CallIdGenerator
from mail.jmap.services.mail.mail import MailService
from mail.jmap.services.mail.mailbox import MailboxService
from mail.jmap.services.mail.submission.email_submission import EmailSubmissionService
from mail.utils.dt import convert_to_utc


class EmailService(MailService):
	"""Service for handling email-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "Email"

	def create(self, emails: list[EmailCreateModel]) -> dict:
		"""
		Public method to create email drafts and optionally submit them, handling batching if the number of emails exceeds the server's maximum allowed in a single 'set' call.
		Returns a dictionary containing the results of draft creation and submission.
		"""

		method_calls = []

		call_id_gen = CallIdGenerator()

		draft_calls, draft_refs = self._create(emails, call_id_gen)
		method_calls.extend(draft_calls)

		submission_service = EmailSubmissionService(self.account, self.connection)
		submission_calls = submission_service._create(emails, draft_refs, call_id_gen)
		method_calls.extend(submission_calls)

		if submission_calls:
			return submission_service._call(submission_service.capabilities, method_calls=method_calls)

		return self._call(self.capabilities, method_calls=method_calls)

	def get(self, ids: list[str], properties: list[str] | None = None) -> list[dict]:
		"""Public method to get emails, handling batching if a list of ids is provided and allowing optional specification of properties to retrieve."""

		properties = properties or [
			"id",
			"blobId",
			"threadId",
			"mailboxIds",
			"keywords",
			"size",
			"receivedAt",
			"sentAt",
			"hasAttachment",
			"subject",
			"preview",
			"from",
			"to",
			"cc",
			"bcc",
			"replyTo",
			"sender",
			"messageId",
			"inReplyTo",
			"references",
			"htmlBody",
			"textBody",
			"bodyValues",
			"preview",
			"attachments",
		]

		results = []
		if ids:
			for batch in self.create_batches(ids, self.max_objects_in_get):
				response = self._get(batch, properties=properties, fetchAllBodyValues=True)

				if method_responses := response.get("methodResponses"):
					results.extend(method_responses[0][1].get("list", []))
		else:
			response = self._get(properties=properties, fetchAllBodyValues=True)
			if method_responses := response.get("methodResponses"):
				results.extend(method_responses[0][1].get("list", []))

		return results

	def update(
		self, emails: list[dict], replace_keywords: bool = False, replace_mailboxes: bool = False
	) -> dict:
		"""Public method to update emails, handling batching if the number of emails exceeds the server's maximum allowed in a single 'set' call. Allows updating of keywords and mailboxIds."""

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(emails, self.max_objects_in_set):
			payload = {}
			for email in batch:
				payload[email["id"]] = {}

				if keywords := email.get("keywords", {}):
					if replace_keywords:
						payload[email["id"]]["keywords"] = keywords
					else:
						payload[email["id"]].update({f"keywords/{k}": v for k, v in keywords.items()})

				if mailbox_ids := email.get("mailbox_ids", {}):
					if replace_mailboxes:
						payload[email["id"]]["mailboxIds"] = mailbox_ids
					else:
						payload[email["id"]].update({f"mailboxIds/{k}": v for k, v in mailbox_ids.items()})

				if not payload[email["id"]]:
					raise ValueError(
						"At least one of 'keywords' or 'mailbox_ids' must be provided for update."
					)

			response = self._update(payload)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	def delete(self, ids: list[str]) -> dict:
		"""Public method to delete emails, handling batching if the number of ids exceeds the server's maximum allowed in a single 'set' call."""

		result = {"destroyed": [], "notDestroyed": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			response = self._delete(batch)

			if method_responses := response.get("methodResponses"):
				result["destroyed"].extend(method_responses[0][1].get("destroyed", []))
				if not_destroyed := method_responses[0][1].get("notDestroyed", {}):
					result["notDestroyed"].update(not_destroyed)

		return result

	def query(
		self, filter: dict | None = None, position: int = 0, limit: int = 50, sort: list[dict] | None = None
	) -> dict:
		"""Public method to query emails, handling batching if the number of results exceeds the server's maximum allowed in a single 'query' call."""

		ids = []
		total = None
		batch_size = min(limit, self.max_objects_in_get)
		sort = sort or [{"property": "receivedAt", "isAscending": False}]

		while len(ids) < limit:
			response = self._query(filter, position, batch_size, sort, calculate_total=total is None)

			if method_responses := response.get("methodResponses"):
				query_response = method_responses[0][1]

				ids.extend(query_response.get("ids", []))

				if total is None:
					total = query_response.get("total", 0)

				if not query_response.get("hasMoreItems", False):
					break

				position += batch_size

		return {"ids": ids[:limit], "total": total}

	def changes(self, since_state: str) -> dict:
		"""Public method to get changes to emails since a given state."""

		response = self._changes(since_state)

		if method_responses := response.get("methodResponses"):
			return method_responses[0][1]

		return {}

	def search(self, text: str, limit: int = 50, separate_requests: bool = False) -> list[str]:
		"""Public method to search for emails matching the given text in subject, to, cc, bcc, body or text."""

		ids: list[str] = []

		def collect_ids(response) -> None:
			"""Helper function to collect unique email IDs from the method responses."""

			for _method, result, _call_id in response.get("methodResponses", []):
				for id in result.get("ids", []):
					if id not in ids:
						ids.append(id)

		filters = [
			{"subject": text},
			{"to": text},
			{"cc": text},
			{"bcc": text},
			{"body": text},
			{"text": text},
		]

		method_calls = [
			[
				f"{self._type}/query",
				{
					"accountId": self.account_id,
					"filter": f,
					"position": 0,
					"limit": limit,
					"sort": [{"property": "receivedAt", "isAscending": False}],
					"calculateTotal": False,
				},
				str(i),
			]
			for i, f in enumerate(filters)
		]

		if separate_requests:
			for call in method_calls:
				collect_ids(self._call(self.capabilities, method_calls=[call]))
		else:
			collect_ids(self._call(self.capabilities, method_calls=method_calls))

		return ids[:limit]

	def query_thread(
		self, filter: dict | None = None, position: int = 0, limit: int = 50, fetch_all: bool = False
	) -> list[str] | dict[str, list[str]]:
		"""Public method to query email threads based on a filter.

		Returns the list of matching thread IDs, or — when `fetch_all` is True — a dict mapping each
		thread ID to its matching (in-mailbox) email IDs.
		"""

		threads: dict[str, list[str]] = {}
		fetched = position
		batch_size = self.max_objects_in_get
		filter = filter or {}

		while len(threads) < limit:
			response = self._call(
				self.capabilities,
				method_calls=[
					[
						f"{self.type}/query",
						{
							"accountId": self.account_id,
							"filter": filter,
							"sort": [{"property": "receivedAt", "isAscending": False}],
							"position": fetched,
							"limit": batch_size,
						},
						"0",
					],
					[
						f"{self.type}/get",
						{
							"accountId": self.account_id,
							"#ids": {"resultOf": "0", "name": f"{self.type}/query", "path": "/ids"},
							"properties": ["id", "threadId"],
						},
						"1",
					],
				],
			)

			emails = response.get("methodResponses", [None, [None, {"list": []}]])[1][1].get("list", [])

			if not emails:
				break

			for email in emails:
				email_id = email["id"]
				thread_id = email["threadId"]

				threads.setdefault(thread_id, []).append(email_id)

				if len(threads) >= limit:
					break

			fetched += batch_size

		return threads if fetch_all else list(threads.keys())

	def get_email_suggestions(self, text: str, limit: int = 5, separate_requests: bool = False) -> list[str]:
		"""
		Get email suggestions based on the given text.

		Args:
		        text (str): The text to search for in email addresses.
		        limit (int): The maximum number of suggestions to return.
		        separate_requests (bool): Whether to make separate requests for each filter.

		Returns:
		        list[str]: A list of email addresses matching the given text.
		"""

		ids: list[str] = []
		addresses: list[str] = []

		def collect_ids(response) -> None:
			"""Helper function to collect unique email IDs from the method responses."""

			for _method, result, _call_id in response.get("methodResponses", []):
				for id in result.get("ids", []):
					if id not in ids:
						ids.append(id)

		filters = [
			{"from": text},
			{"to": text},
			{"cc": text},
			{"bcc": text},
		]

		method_calls = [
			[
				f"{self._type}/query",
				{
					"accountId": self.account_id,
					"filter": f,
					"position": 0,
					"limit": limit,
					"sort": [{"property": "receivedAt", "isAscending": False}],
					"calculateTotal": False,
				},
				str(i),
			]
			for i, f in enumerate(filters)
		]

		if separate_requests:
			for call in method_calls:
				collect_ids(self._call(self.capabilities, method_calls=[call]))
		else:
			collect_ids(self._call(self.capabilities, method_calls=method_calls))

		if not ids:
			return addresses

		emails = self.get(ids, properties=["from", "to", "cc", "bcc"])

		for email in emails:
			for field in ("from", "to", "cc", "bcc"):
				for addr in email.get(field) or []:
					email_address = addr.get("email")
					if email_address and text.lower() in email_address.lower() not in addresses:
						addresses.append(email_address)

		return addresses[:limit]

	def _create(self, emails: list[EmailCreateModel], call_id_gen: CallIdGenerator) -> tuple[list, dict]:
		"""Helper method to create email drafts for the given list of EmailCreateModel instances and return the method calls for the JMAP request along with a mapping of creation IDs to draft references."""

		method_calls = []
		draft_refs = {}

		mailbox_service = MailboxService(self.account, self.connection)
		draft_mailbox_id = mailbox_service.get_mailbox_id_by_role(
			"drafts", create_if_not_exists=True, raise_exception=True
		)

		for email in emails:
			draft_ref = f"draft-{email.creation_id}"
			draft_refs[email.creation_id] = draft_ref

			# --------------------------------------------------
			# RAW MESSAGE → Email/import
			# --------------------------------------------------

			if email.raw_message:
				blob = self.upload_blob(email.raw_message.encode("utf-8"), content_type="message/rfc822")

				method_calls.append(
					[
						f"{self.type}/import",
						{
							"accountId": self.account_id,
							"emails": {
								draft_ref: {
									"blobId": blob["blobId"],
									"mailboxIds": {draft_mailbox_id: True},
									"keywords": {"$draft": True, "$seen": True},
								}
							},
						},
						call_id_gen.next(),
					]
				)

				# Destroy old email if existing_id is provided.
				if email.existing_id:
					method_calls.append(
						[
							f"{self.type}/set",
							{
								"accountId": self.account_id,
								"destroy": [email.existing_id],
							},
							call_id_gen.next(),
						]
					)

			# --------------------------------------------------
			# NORMAL DRAFT → Email/set
			# --------------------------------------------------

			else:
				payload = {
					"accountId": self.account_id,
					"create": {draft_ref: self._get_draft(email, draft_mailbox_id)},
				}

				if email.existing_id:
					payload["destroy"] = [email.existing_id]

				method_calls.append([f"{self.type}/set", payload, call_id_gen.next()])

		return method_calls, draft_refs

	@staticmethod
	def _get_recipients(
		recipients: list[EmailRecipient], kind: Literal["to", "cc", "bcc"]
	) -> list[dict[str, str | None]]:
		"""Helper function to filter recipients by type and format them for the JMAP payload."""

		return [{"name": r.name, "email": r.email} for r in recipients if r.type == kind]

	@staticmethod
	def _get_draft(email: EmailCreateModel, draft_mailbox_id: str) -> dict:
		"""Helper function to build the draft payload for the email creation."""

		draft = {
			"mailboxIds": {draft_mailbox_id: True},
			"keywords": {"$draft": True, "$seen": True},
			"from": [{"name": email.from_name, "email": email.from_email}],
		}

		# Add TO/CC/BCC
		if email.recipients:
			for kind in ("to", "cc", "bcc"):
				if rcpts := EmailService._get_recipients(email.recipients, kind):
					draft[kind] = rcpts

		if email.subject:
			draft["subject"] = email.subject

		# Headers
		if email.sent_at:
			draft["sentAt"] = convert_to_utc(email.sent_at).isoformat()
		if email.message_id:
			draft["header:Message-ID"] = f"<{email.message_id}>"

		draft.update(
			{
				"header:User-Agent": f"Frappe Mail v{__version__} (Frappe v{frappe.__version__})",
				"header:X-Mailer": "Frappe Mail",
				"header:X-Mail-Queue": str(email.creation_id),
			}
		)

		if email.reply_to:
			draft["header:Reply-To"] = ", ".join(f'"{r.name}" <{r.email}>' for r in email.reply_to)

		if email.in_reply_to:
			draft["header:In-Reply-To"] = f"<{email.in_reply_to}>"

		if email.headers:
			for header in email.headers:
				draft[f"header:{header.name}"] = header.value

		# Body parts
		draft["bodyValues"] = {}

		if email.text_body:
			draft["textBody"] = [{"partId": "text", "type": "text/plain"}]
			draft["bodyValues"]["text"] = {
				"value": email.text_body,
				"charset": "utf-8",
				"isTruncated": False,
			}

		if email.html_body:
			draft["htmlBody"] = [{"partId": "html", "type": "text/html"}]
			draft["bodyValues"]["html"] = {
				"value": email.html_body,
				"charset": "utf-8",
				"isTruncated": False,
			}

		# Attachments
		if email.attachments:
			draft["attachments"] = [
				{
					"name": a.name,
					"type": a.type,
					"cid": a.cid,
					"blobId": a.blob_id,
					"disposition": a.disposition,
				}
				for a in email.attachments
			]

		return draft
