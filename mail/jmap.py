import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import cached_property
from typing import Any, Literal
from urllib.parse import urljoin

import frappe
import requests
from frappe import _
from frappe.utils import create_batch

from mail import __version__
from mail.utils.cache import get_cluster_for_tenant
from mail.utils.dt import convert_to_utc, utcnow
from mail.utils.validation import has_permission_for_account


class JMAPClient:
	"""JMAP Client for interacting with JMAP servers."""

	def __init__(self, host: str, username: str, password: str) -> None:
		"""Initialize the JMAP client."""

		self.__host = host
		self.__config = None
		self.__session = requests.Session()
		self.__session.auth = (username, password)

		self._discover_config()

	def _discover_config(self) -> None:
		"""Discover JMAP configuration from the server."""

		well_known_url = urljoin(self.__host, "/.well-known/jmap")
		response = self.__session.get(well_known_url, headers={"Accept": "application/json"})
		raise_for_status(response)
		self.__config = response.json()

	def _validate_capabilities(self, capabilities: list[str]) -> None:
		"""Validate the requested capabilities against the server's capabilities."""

		for capability in capabilities:
			if capability not in self.capabilities:
				raise ValueError(f"Unsupported capability: {capability}")

	def _validate_method_calls(self, method_calls: list[list]) -> None:
		"""Validate the method calls against the server's capabilities."""

		if self.max_calls_in_request and len(method_calls) > self.max_calls_in_request:
			frappe.throw(
				_("Number of method calls exceeds the maximum allowed: {0}.").format(
					self.max_calls_in_request
				)
			)

		call_ids = []
		for method_call in method_calls:
			if not isinstance(method_call, list) or len(method_call) != 3:
				raise ValueError("Method call must be a list of [method_name, arguments, call_id]")

			if (
				not isinstance(method_call[0], str)
				or not isinstance(method_call[1], dict)
				or not isinstance(method_call[2], str)
			):
				raise ValueError("Method call must be a list of [string, dict, string]")

			if method_call[2] in call_ids:
				raise ValueError(f"Duplicate call ID: {method_call[2]}")

			call_ids.append(method_call[2])

	def _make_request(self, using: list[str], method_calls: list[list]) -> Any:
		"""Make a request to the JMAP server."""

		self._validate_capabilities(using)
		self._validate_method_calls(method_calls)

		headers = {"Content-Type": "application/json", "Accept": "application/json"}
		payload = {"using": using, "methodCalls": method_calls}
		response = self.__session.post(
			self.api_url, headers=headers, data=json.dumps(payload, ensure_ascii=False), timeout=(5, 30)
		)
		raise_for_status(response)

		return response.json()

	@property
	def capabilities(self) -> dict:
		"""Returns the capabilities of the JMAP server."""

		return self.__config["capabilities"]

	@property
	def max_size_upload(self) -> int:
		"""Returns the maximum size of uploads supported by the JMAP server."""

		return self.capabilities["urn:ietf:params:jmap:core"]["maxSizeUpload"]

	@property
	def max_concurrent_upload(self) -> int:
		"""Returns the maximum number of concurrent uploads supported by the JMAP server."""

		return self.capabilities["urn:ietf:params:jmap:core"]["maxConcurrentUpload"]

	@property
	def max_size_request(self) -> int:
		"""Returns the maximum size of a request supported by the JMAP server."""

		return self.capabilities["urn:ietf:params:jmap:core"]["maxSizeRequest"]

	@property
	def max_concurrent_requests(self) -> int:
		"""Returns the maximum number of concurrent requests supported by the JMAP server."""

		return self.capabilities["urn:ietf:params:jmap:core"]["maxConcurrentRequests"]

	@property
	def max_calls_in_request(self) -> int:
		"""Returns the maximum number of calls in a single request."""

		return self.capabilities["urn:ietf:params:jmap:core"]["maxCallsInRequest"]

	@property
	def max_objects_in_get(self) -> int:
		"""Returns the maximum number of objects in a single get request."""

		return self.capabilities["urn:ietf:params:jmap:core"]["maxObjectsInGet"]

	@property
	def max_objects_in_set(self) -> int:
		"""Returns the maximum number of objects in a single set request."""

		return self.capabilities["urn:ietf:params:jmap:core"]["maxObjectsInSet"]

	@property
	def supports_websocket(self) -> bool:
		"""Returns True if the JMAP server supports WebSocket, False otherwise."""

		return "urn:ietf:params:jmap:websocket" in self.capabilities

	@property
	def websocket_url(self) -> str | None:
		"""Returns the WebSocket URL for the JMAP server, if supported."""

		if self.supports_websocket:
			return self.capabilities["urn:ietf:params:jmap:websocket"]["url"]

	@property
	def websocket_supports_push(self) -> bool:
		"""Returns True if the JMAP server supports WebSocket push, False otherwise."""

		if self.supports_websocket:
			return self.capabilities["urn:ietf:params:jmap:websocket"].get("supportsPush", False)
		return False

	@property
	def accounts(self) -> dict:
		"""Returns the accounts for the logged-in user."""

		return self.__config["accounts"]

	@property
	def account_ids(self) -> list[str]:
		"""Returns the list of account IDs for the logged-in user."""

		return list(self.__config["accounts"].keys())

	@property
	def has_multiple_accounts(self) -> bool:
		"""Returns True if the user has multiple accounts, False otherwise."""

		return len(self.account_ids) > 1

	@property
	def primary_accounts(self) -> dict:
		"""Returns the primary accounts for the logged-in user."""

		return self.__config["primaryAccounts"]

	@property
	def primary_account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.primary_accounts["urn:ietf:params:jmap:mail"]

	@property
	def username(self) -> str:
		"""Returns the username of the logged-in user."""

		return self.__config["username"]

	@property
	def api_url(self) -> str:
		"""Returns the API URL for the JMAP server."""

		return self.__config["apiUrl"]

	@property
	def download_url(self) -> str:
		"""Returns the download URL for the JMAP server."""

		return self.__config["downloadUrl"]

	@property
	def upload_url(self) -> str:
		"""Returns the upload URL for the JMAP server."""

		return self.__config["uploadUrl"]

	@property
	def event_source_url(self) -> str:
		"""Returns the event source URL for the JMAP server."""

		return self.__config["eventSourceUrl"]

	@property
	def state(self) -> dict:
		"""Returns the state of the JMAP server."""

		return self.__config["state"]

	@property
	def mailboxes(self) -> list[dict]:
		"""Returns the mailboxes for the logged-in user."""

		def generator() -> list[dict]:
			mailboxes = frappe.db.get_all("Mailbox", {"account": self.__session.auth[0]})
			return [
				{
					"id": mailbox["id"],
					"name": mailbox["name"],
					"role": mailbox["role"],
					"_name": mailbox["_name"],
					"_parent": mailbox["_parent"],
					"parent_id": mailbox["parent_id"],
					"subscribed": mailbox["subscribed"],
					"_sort_order": mailbox["_sort_order"],
				}
				for mailbox in mailboxes
			]

		return frappe.cache.hget("jmap:mailboxes", self.__session.auth[0], generator)

	@property
	def identities(self) -> list[dict]:
		"""Returns the identities for the logged-in user."""

		def generator() -> list[dict]:
			return self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[["Identity/get", {"accountId": self.primary_account_id}, "0"]],
			)["methodResponses"][0][1]["list"]

		return frappe.cache.hget("jmap:identities", self.__session.auth[0], generator)

	@cached_property
	def address_books(self) -> list[dict]:
		"""Returns the address books for the logged-in user."""

		address_books = frappe.db.get_all("Address Book", {"account": self.__session.auth[0]})
		return address_books

	# -------------------------------
	# Mailbox
	# -------------------------------

	def mailbox_create(
		self,
		creation_id: str,
		name: str,
		role: str | None = None,
		parent: str | None = None,
		sort_order: int = 0,
		subscribed: bool = True,
	) -> dict:
		"""Creates a mailbox with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"Mailbox/set",
					{
						"accountId": self.primary_account_id,
						"create": {
							creation_id: {
								"name": name,
								"role": role or None,
								"parentId": parent or None,
								"sortOrder": sort_order or 0,
								"isSubscribed": subscribed or False,
							}
						},
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def mailbox_get(self, ids: list[str] | None = None) -> list[dict]:
		"""Returns the mailboxes for the provided mailbox IDs."""

		def fetch(ids_batch: list[str] | None) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Mailbox/get",
						{
							"accountId": self.primary_account_id,
							"ids": ids_batch,
						},
						"0",
					]
				],
			)
			return response["methodResponses"][0][1]["list"]

		if ids and len(ids) > self.max_objects_in_get:
			mailboxes = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				mailboxes.extend(fetch(ids_batch))
			return mailboxes

		return fetch(ids)

	def mailbox_update(
		self,
		id: str,
		name: str,
		role: str | None = None,
		parent: str | None = None,
		sort_order: int = 0,
		subscribed: bool = True,
	) -> dict:
		"""Updates the mailbox with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"Mailbox/set",
					{
						"accountId": self.primary_account_id,
						"update": {
							id: {
								"name": name,
								"role": role or None,
								"parentId": parent or None,
								"sortOrder": sort_order or 0,
								"isSubscribed": subscribed or False,
							}
						},
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def mailbox_delete(self, ids: list[str], remove_emails: bool = False) -> dict:
		"""Destroys the mailboxes with the given IDs."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Mailbox/set",
						{
							"accountId": self.primary_account_id,
							"destroy": ids_batch,
							"onDestroyRemoveEmails": remove_emails,
						},
						"0",
					]
				],
			)

			result["destroyed"].extend(response["methodResponses"][0][1].get("destroyed", []))
			if not_destroyed := response["methodResponses"][0][1].get("notDestroyed", {}):
				result["notDestroyed"].update(not_destroyed)

		return result

	def get_mailbox_id_by_role(self, role: str, raise_exception: bool = False) -> str | None:
		"""Returns the mailbox ID for the given role."""

		for mailbox in self.mailboxes:
			mailbox_role = mailbox.get("role") or ""
			if role and mailbox_role.lower() == role.lower():
				return mailbox["id"]

		if raise_exception:
			frappe.throw(
				_("Mailbox with role {0} not found for account {1}.").format(
					frappe.bold(role), frappe.bold(self.__session.auth[0])
				)
			)

	def get_mailbox_role_by_id(self, id: str, raise_exception: bool = False) -> str | None:
		"""Returns the mailbox role for the given ID."""

		for mailbox in self.mailboxes:
			if mailbox["id"] == id:
				return mailbox["role"]

		if raise_exception:
			frappe.throw(
				_("Mailbox with ID {0} not found for account {1}.").format(
					frappe.bold(id), frappe.bold(self.__session.auth[0])
				)
			)

	def get_mailbox_name_by_id(self, id: str, raise_exception: bool = False) -> str | None:
		"""Returns the mailbox name for the given ID."""

		for mailbox in self.mailboxes:
			if id and mailbox["id"] == id:
				return mailbox["_name"]

		if raise_exception:
			frappe.throw(
				_("Mailbox with ID {0} not found for account {1}.").format(
					frappe.bold(id), frappe.bold(self.__session.auth[0])
				)
			)

		# -------------------------------

	# -------------------------------
	# Email/Thread
	# -------------------------------

	def email_create(
		self,
		creation_id: str,
		from_email: str,
		recipients: list[dict],
		from_name: str | None = None,
		subject: str | None = None,
		sent_at: str | None = None,
		message_id: str | None = None,
		reply_to: list[dict] | None = None,
		in_reply_to: str | None = None,
		headers: dict | None = None,
		text_body: str | None = None,
		html_body: str | None = None,
		attachments: list[dict] | None = None,
		raw_message: str | None = None,
		existing_id: str | None = None,
		save_as_draft: bool = False,
		priority: int = 0,
		destroy_after_submit: bool = False,
		forwarded_id: str | None = None,
		reply_to_id: str | None = None,
	) -> dict:
		"""
		Creates and submits an email.
		If `save_as_draft=True`, the email is only created as a draft and not submitted.
		"""

		# ----------------------------------------------------------------------
		# HELPERS
		# ----------------------------------------------------------------------

		def filter_recipients(kind: Literal["to", "cc", "bcc"]) -> list[dict[str, str | None]]:
			return [
				{"name": r.get("name", r["display_name"]), "email": r["email"]}
				for r in recipients
				if r["type"].lower() == kind
			]

		def build_draft_payload(draft_mbox: str) -> dict:
			payload = {
				"mailboxIds": {draft_mbox: True},
				"keywords": {"$draft": True, "$seen": True},
				"from": [{"name": from_name, "email": from_email}],
			}

			# Add TO/CC/BCC
			for kind in ("to", "cc", "bcc"):
				if rcpts := filter_recipients(kind):
					payload[kind] = rcpts

			if subject:
				payload["subject"] = subject

			# Headers
			payload.update(
				{
					"sentAt": convert_to_utc(sent_at).isoformat(),
					"header:Message-ID": f"<{message_id}>",
					"header:User-Agent": f"Frappe Mail v{__version__} (Frappe v{frappe.__version__})",
					"header:X-Mailer": "Frappe Mail",
					"header:X-Mail-Queue": str(creation_id),
				}
			)

			if reply_to:
				payload["header:Reply-To"] = ", ".join(
					f'"{r.get("name", r["display_name"])}" <{r["email"]}>' for r in reply_to
				)

			if in_reply_to:
				payload["header:In-Reply-To"] = f"<{in_reply_to}>"

			if headers:
				for k, v in headers.items():
					payload[f"header:{k}"] = str(v)

			# Body parts
			payload["bodyValues"] = {}

			if text_body:
				payload["textBody"] = [{"partId": "text", "type": "text/plain"}]
				payload["bodyValues"]["text"] = {"value": text_body, "charset": "utf-8", "isTruncated": False}

			if html_body:
				payload["htmlBody"] = [{"partId": "html", "type": "text/html"}]
				payload["bodyValues"]["html"] = {"value": html_body, "charset": "utf-8", "isTruncated": False}

			# Attachments
			if attachments:
				payload["attachments"] = [
					{
						"name": a.get("name", a["filename"]),
						"type": a["type"],
						"cid": a["cid"],
						"blobId": a["blob_id"],
						"disposition": a["disposition"],
					}
					for a in attachments
				]

			return payload

		draft_mailbox_id = self.get_mailbox_id_by_role("drafts", raise_exception=True)
		sent_mailbox_id = self.get_mailbox_id_by_role("sent", raise_exception=not save_as_draft)

		identity_id = next((i["id"] for i in self.identities if i["email"] == from_email), None)
		if not identity_id:
			frappe.throw(
				_("No identity found for email {0} in account {1}.").format(
					frappe.bold(from_email), frappe.bold(self.__session.auth[0])
				)
			)

		using = ["urn:ietf:params:jmap:mail"]
		method_calls = []
		call_id = 0

		draft_ref = f"draft-{creation_id}"
		submit_ref = f"submit-{creation_id}"

		# ----------------------------------------------------------------------
		# STEP 1 — CREATE DRAFT
		# ----------------------------------------------------------------------

		if raw_message:
			blob = self.upload_blob(raw_message.encode("utf-8"), content_type="message/rfc822")
			method_calls.append(
				[
					"Email/import",
					{
						"accountId": self.primary_account_id,
						"emails": {
							draft_ref: {
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

			if existing_id:
				method_calls.append(
					[
						"Email/set",
						{
							"accountId": self.primary_account_id,
							"destroy": [existing_id],
						},
						str(call_id),
					]
				)
				call_id += 1

		else:
			method_calls.append(
				[
					"Email/set",
					{
						"accountId": self.primary_account_id,
						"create": {draft_ref: build_draft_payload(draft_mailbox_id)},
						"destroy": [existing_id] if existing_id else None,
					},
					str(call_id),
				]
			)
			call_id += 1

		if save_as_draft:
			return self._make_request(using=using, method_calls=method_calls)

		# ----------------------------------------------------------------------
		# STEP 2 — SUBMIT EMAIL
		# ----------------------------------------------------------------------

		using.append("urn:ietf:params:jmap:submission")

		submission = {
			"identityId": identity_id,
			"emailId": f"#{draft_ref}",
			"envelope": {
				"mailFrom": {
					"email": from_email,
					"parameters": {
						"RET": "FULL",
						"ENVID": creation_id,
						"MT-PRIORITY": str(priority),
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
					for rcpt in sorted({r["email"] for r in recipients})
				],
			},
		}

		submit_call = [
			"EmailSubmission/set",
			{
				"accountId": self.primary_account_id,
				"create": {submit_ref: submission},
			},
			str(call_id),
		]

		# ----------------------------------------------------------------------
		# STEP 3 — SUCCESS UPDATES
		# ----------------------------------------------------------------------

		updates = {}

		if destroy_after_submit:
			submit_call[1]["onSuccessDestroyEmail"] = [f"#{submit_ref}"]
		else:
			updates[f"#{submit_ref}"] = {
				f"mailboxIds/{draft_mailbox_id}": None,
				f"mailboxIds/{sent_mailbox_id}": True,
				"keywords/$draft": None,
				"keywords/$seen": True,
			}

		# Forward/reply keywords
		for id, keyword in [(forwarded_id, "$forwarded"), (reply_to_id, "$answered")]:
			if id:
				updates.setdefault(id, {})[f"keywords/{keyword}"] = True

		if updates:
			submit_call[1]["onSuccessUpdateEmail"] = updates

		method_calls.append(submit_call)

		return self._make_request(using=using, method_calls=method_calls)

	def email_query(
		self, filter: dict | None = None, position: int = 0, limit: int = 50, sort: list[dict] | None = None
	) -> dict:
		"""Query emails in batches until reaching the limit."""

		ids = []
		total = None
		batch_size = min(limit, self.max_objects_in_get)
		sort = sort or [{"property": "receivedAt", "isAscending": False}]

		while len(ids) < limit:
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Email/query",
						{
							"accountId": self.primary_account_id,
							"filter": filter or {},
							"position": position,
							"limit": batch_size,
							"sort": sort,
							"calculateTotal": True if total is None else False,
						},
						"0",
					]
				],
			)
			result = response["methodResponses"][0][1]

			if total is None:
				total = result["total"]

			_ids = result["ids"]
			if not _ids:
				break

			ids.extend(_ids)
			position += len(_ids)

			if len(_ids) < batch_size:
				break

		return {"ids": ids[:limit], "total": total}

	def thread_query(
		self, filter: dict | None = None, position: int = 0, limit: int = 50, fetch_all: bool = False
	) -> list[str] | dict[str, list]:
		"""Returns threads based on the provided filter."""

		threads: dict[str, list[str]] = {}
		fetched = position
		batch_size = self.max_objects_in_get

		while len(threads) < limit:
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Email/query",
						{
							"accountId": self.primary_account_id,
							"filter": filter or {},
							"sort": [{"property": "receivedAt", "isAscending": False}],
							"position": fetched,
							"limit": batch_size,
						},
						"0",
					],
					[
						"Email/get",
						{
							"accountId": self.primary_account_id,
							"#ids": {"resultOf": "0", "name": "Email/query", "path": "/ids"},
							"properties": ["id", "threadId"],
						},
						"1",
					],
				],
			)

			email_list = response["methodResponses"][1][1]["list"]
			if not email_list:
				break

			for email in email_list:
				threads.setdefault(email["threadId"], []).append(email["id"])
				if len(threads) >= limit:
					break

			fetched += batch_size

		if not fetch_all:
			return [ids[0] for ids in threads.values()]

		return threads

	def relevance_search(self, text: str, limit: int = 50, batch_call: bool = True) -> list[str]:
		"""Returns emails matching the given text in subject, to, cc, bcc, body or text."""

		def _extract_ids_from_response(response: dict) -> list[str]:
			ids = []
			for method_response in response["methodResponses"]:
				_method, result, _call_id = method_response
				for id in result.get("ids", []):
					if id not in ids:
						ids.append(id)
			return ids

		filters = [
			{"subject": text},
			{"to": text},
			{"cc": text},
			{"bcc": text},
			{"body": text},
			{"text": text},
		]

		method_calls = []
		for i, filter in enumerate(filters):
			method_calls.append(
				[
					"Email/query",
					{
						"accountId": self.primary_account_id,
						"filter": filter,
						"position": 0,
						"limit": limit,
						"sort": [{"property": "receivedAt", "isAscending": False}],
						"calculateTotal": False,
					},
					str(i),
				]
			)

		ids = []
		if batch_call:
			response = self._make_request(using=["urn:ietf:params:jmap:mail"], method_calls=method_calls)
			ids = _extract_ids_from_response(response)
		else:
			for method_call in method_calls:
				response = self._make_request(using=["urn:ietf:params:jmap:mail"], method_calls=[method_call])
				for id in _extract_ids_from_response(response):
					if id not in ids:
						ids.append(id)

				if len(ids) >= limit:
					break

		return ids[:limit]

	def email_get(self, ids: list[str], properties: list[str] | None = None) -> tuple[list[dict], str]:
		"""Returns the emails for the provided email IDs."""

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
			"attachments",
		]

		emails = []
		state = None
		for ids_batch in create_batch(ids, self.max_objects_in_get):
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Email/get",
						{
							"accountId": self.primary_account_id,
							"ids": ids_batch,
							"properties": properties,
							"fetchAllBodyValues": True,
						},
						"0",
					]
				],
			)
			emails.extend(response["methodResponses"][0][1]["list"])
			state = response["methodResponses"][0][1]["state"]

		return emails, state

	def thread_get(self, ids: list[str]) -> dict[str, list]:
		"""Returns the threads for the provided thread IDs."""

		result = {}
		for ids_batch in create_batch(ids, self.max_objects_in_get):
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Thread/get",
						{
							"accountId": self.primary_account_id,
							"ids": ids_batch,
							"properties": ["emailIds"],
						},
						"0",
					]
				],
			)

			if threads := response["methodResponses"][0][1]["list"]:
				result.update({thread["id"]: thread["emailIds"] for thread in threads})

		return result

	def email_update(
		self, ids: list[str], mailbox_id: str | None = None, keywords: dict[str, bool] | None = None
	) -> dict:
		"""Update email mailbox or keywords."""

		if not mailbox_id and not keywords:
			frappe.throw(_("Either mailbox_id or keywords must be provided."))

		result = {"updated": {}, "notUpdated": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			updates = {}
			for id in ids_batch:
				update = {}
				if keywords:
					update.update({f"keywords/{keyword}": value for keyword, value in keywords.items()})
				if mailbox_id:
					update["mailboxIds"] = {mailbox_id: True}

				updates[id] = update

			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Email/set",
						{
							"accountId": self.primary_account_id,
							"update": updates,
						},
						"0",
					]
				],
			)

			result["updated"].update(response["methodResponses"][0][1].get("updated", {}))
			if not_updated := response["methodResponses"][0][1].get("notUpdated", {}):
				result["notUpdated"].update(not_updated)

		return result

	def email_delete(self, ids: list[str]) -> dict:
		"""Destroy emails."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Email/set",
						{
							"accountId": self.primary_account_id,
							"destroy": ids_batch,
						},
						"0",
					]
				],
			)

			result["destroyed"].extend(response["methodResponses"][0][1].get("destroyed", []))
			if not_destroyed := response["methodResponses"][0][1].get("notDestroyed", {}):
				result["notDestroyed"].update(not_destroyed)

		return result

	def email_changes(self, since_state: str) -> dict:
		"""Returns the changes in emails since the provided state."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"Email/changes",
					{
						"accountId": self.primary_account_id,
						"sinceState": since_state,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	# -------------------------------
	# Vacation Response
	# -------------------------------

	def vacation_response_get(self) -> dict:
		"""Returns the vacation response for the primary account."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail", "urn:ietf:params:jmap:vacationresponse"],
			method_calls=[
				[
					"VacationResponse/get",
					{
						"accountId": self.primary_account_id,
					},
					"0",
				]
			],
		)

		vacation_responses = response["methodResponses"][0][1]["list"]
		return vacation_responses[0] if vacation_responses else {}

	def vacation_response_update(
		self,
		enabled: bool,
		from_date: str | None = None,
		to_date: str | None = None,
		subject: str | None = None,
		text_body: str | None = None,
		html_body: str | None = None,
	) -> dict:
		"""Sets the vacation response for the primary account."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail", "urn:ietf:params:jmap:vacationresponse"],
			method_calls=[
				[
					"VacationResponse/set",
					{
						"accountId": self.primary_account_id,
						"update": {
							"singleton": {
								"isEnabled": enabled,
								"fromDate": from_date or None,
								"toDate": to_date or None,
								"subject": subject or None,
								"textBody": text_body or None,
								"htmlBody": html_body or None,
							}
						},
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	# -------------------------------
	# Push Subscription
	# -------------------------------

	def push_subscription_create(
		self, creation_id: str, device_client_id: str, url: str, types: list[str] | None = None
	) -> dict:
		"""Creates a push subscription."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"PushSubscription/set",
					{
						"create": {
							creation_id: {
								"deviceClientId": device_client_id,
								"url": url,
								"types": types,
							}
						},
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def push_subscription_get(self, ids: list[str] | None = None) -> list[dict]:
		"""Returns the push subscriptions for the provided subscription IDs."""

		def fetch(ids_batch: list[str] | None) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"PushSubscription/get",
						{
							"ids": ids_batch,
						},
						"0",
					]
				],
			)
			return response["methodResponses"][0][1]["list"]

		if ids and len(ids) > self.max_objects_in_get:
			subscriptions = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				subscriptions.extend(fetch(ids_batch))
			return subscriptions

		return fetch(ids)

	def push_subscription_update(
		self, id: str, verification_code: str | None = None, expires: str | None = None
	) -> list[list]:
		"""Updates the push subscription with either a new verification code or expiration date."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"PushSubscription/set",
					{
						"update": {
							id: {"verificationCode": verification_code}
							if verification_code
							else {"expires": expires}
						},
					},
					"0",
				],
				[
					"PushSubscription/get",
					{
						"ids": [id],
					},
					"1",
				],
			],
		)

		return response["methodResponses"]

	def push_subscription_delete(self, ids: list[str]) -> dict:
		"""Destroys push subscriptions."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"PushSubscription/set",
						{
							"destroy": ids_batch,
						},
						"0",
					]
				],
			)

			result["destroyed"].extend(response["methodResponses"][0][1].get("destroyed", []))
			if not_destroyed := response["methodResponses"][0][1].get("notDestroyed", {}):
				result["notDestroyed"].update(not_destroyed)

		return result

	# -------------------------------
	# Address Book & Contact Card
	# -------------------------------

	def address_book_create(
		self,
		creation_id: str,
		name: str,
		description: str | None = None,
		sort_order: int = 0,
		default: bool = False,
		subscribed: bool = True,
	) -> dict:
		"""Creates a address book with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:contacts"],
			method_calls=[
				[
					"AddressBook/set",
					{
						"accountId": self.primary_account_id,
						"create": {
							creation_id: {
								"name": name,
								"description": description or None,
								"sortOrder": sort_order or 0,
								"isSubscribed": subscribed or False,
							}
						},
						"onSuccessSetIsDefault": f"#{creation_id}" if default else None,
					},
					"0",
				]
			],
		)
		return response["methodResponses"][0][1]

	def address_book_get(self, ids: list[str] | None = None) -> list[dict]:
		"""Returns the address books for the provided address book IDs."""

		def fetch(ids_batch: list[str] | None) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:contacts"],
				method_calls=[
					[
						"AddressBook/get",
						{
							"accountId": self.primary_account_id,
							"ids": ids_batch,
						},
						"0",
					]
				],
			)
			return response["methodResponses"][0][1]["list"]

		if ids and len(ids) > self.max_objects_in_get:
			address_books = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				address_books.extend(fetch(ids_batch))
			return address_books

		return fetch(ids)

	def address_book_update(
		self,
		id: str,
		name: str,
		description: str | None = None,
		sort_order: int = 0,
		default: bool = False,
		subscribed: bool = True,
	) -> dict:
		"""Updates the address book with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:contacts"],
			method_calls=[
				[
					"AddressBook/set",
					{
						"accountId": self.primary_account_id,
						"update": {
							id: {
								"name": name,
								"description": description or None,
								"sortOrder": sort_order or 0,
								"isSubscribed": subscribed or False,
							}
						},
						"onSuccessSetIsDefault": id if default else None,
					},
					"0",
				]
			],
		)
		return response["methodResponses"][0][1]

	def address_book_delete(self, ids: list[str], remove_contents: bool = False) -> dict:
		"""Destroys the address books with the given IDs."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:contacts"],
				method_calls=[
					[
						"AddressBook/set",
						{
							"accountId": self.primary_account_id,
							"destroy": ids_batch,
							"onDestroyRemoveContents": remove_contents,
						},
						"0",
					]
				],
			)

			result["destroyed"].extend(response["methodResponses"][0][1].get("destroyed", []))
			if not_destroyed := response["methodResponses"][0][1].get("notDestroyed", {}):
				result["notDestroyed"].update(not_destroyed)

		return result

	def contact_card_create(
		self,
		creation_id: str,
		address_book_ids: list[str],
		full_name: str | None = None,
		emails: list[dict] | None = None,
		phones: list[dict] | None = None,
		addresses: list[dict] | None = None,
		kind: str = "individual",
	) -> dict:
		"""Creates a contact card with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:contacts"],
			method_calls=[
				[
					"ContactCard/set",
					{
						"accountId": self.primary_account_id,
						"create": {
							creation_id: {
								"addressBookIds": {id: True for id in address_book_ids},
								"kind": kind,
								"name": _get_name_map(full_name),
								"emails": _get_emails_map(emails),
								"phones": _get_phones_map(phones),
								"addresses": _get_addresses_map(addresses),
								"created": utcnow(),
								"updated": utcnow(),
							}
						},
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def contact_card_query(
		self, filter: dict | None = None, position: int = 0, limit: int = 50, sort: list[dict] | None = None
	) -> dict:
		"""Query contact cards in batches until reaching the limit."""

		ids = []
		total = None
		batch_size = min(limit, self.max_objects_in_get)

		while len(ids) < limit:
			response = self._make_request(
				using=["urn:ietf:params:jmap:contacts"],
				method_calls=[
					[
						"ContactCard/query",
						{
							"accountId": self.primary_account_id,
							"filter": filter or {},
							"position": position,
							"limit": batch_size,
							"sort": sort or [],
							"calculateTotal": True if total is None else False,
						},
						"0",
					]
				],
			)
			result = response["methodResponses"][0][1]

			if total is None:
				total = result["total"]

			_ids = result["ids"]
			if not _ids:
				break

			ids.extend(_ids)
			position += len(_ids)

			if len(_ids) < batch_size:
				break

		return {"ids": ids[:limit], "total": total}

	def contact_card_get(
		self, ids: list[str] | None = None, properties: list[str] | None = None
	) -> list[dict]:
		"""Returns the contact cards for the provided contact card IDs."""

		def fetch(ids_batch: list[str] | None, properties: list[str]) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:contacts"],
				method_calls=[
					[
						"ContactCard/get",
						{
							"accountId": self.primary_account_id,
							"ids": ids_batch,
							"properties": properties,
						},
						"0",
					]
				],
			)
			return response["methodResponses"][0][1]["list"]

		properties = properties or [
			# --- JMAP-specific ---
			"id",
			"addressBookIds",
			"blobId",
			# --- JSContact core fields ---
			"uid",
			"kind",
			"prodId",
			"version",
			"created",
			"updated",
			"fullName",
			"name",
			"nickNames",
			"categories",
			"notes",
			"anniversaries",
			"urls",
			"relatedTo",
			"organizations",
			"titles",
			"roles",
			"emails",
			"phones",
			"addresses",
			"onlineServices",
			"preferredLanguages",
			"speakToAs",
			"gender",
			"timeZones",
			"photos",
			"members",
			"preferredContactChannels",
			"localizations",
			"extensions",
		]

		if ids and len(ids) > self.max_objects_in_get:
			contact_cards = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				contact_cards.extend(fetch(ids_batch, properties))
			return contact_cards

		return fetch(ids, properties)

	def contact_card_update(
		self,
		id: str,
		address_book_ids: list[str],
		full_name: str | None = None,
		emails: list[dict] | None = None,
		phones: list[dict] | None = None,
		addresses: list[dict] | None = None,
		kind: str = "individual",
	) -> dict:
		"""Updates the contact card with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:contacts"],
			method_calls=[
				[
					"ContactCard/set",
					{
						"accountId": self.primary_account_id,
						"update": {
							id: {
								"addressBookIds": {id: True for id in address_book_ids},
								"kind": kind,
								"name": _get_name_map(full_name),
								"emails": _get_emails_map(emails),
								"phones": _get_phones_map(phones),
								"addresses": _get_addresses_map(addresses),
								"updated": utcnow(),
							}
						},
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def contact_card_delete(self, ids: list[str]) -> dict:
		"""Destroys the contact cards with the given IDs."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:contacts"],
				method_calls=[
					[
						"ContactCard/set",
						{
							"accountId": self.primary_account_id,
							"destroy": ids_batch,
						},
						"0",
					]
				],
			)

			result["destroyed"].extend(response["methodResponses"][0][1].get("destroyed", []))
			if not_destroyed := response["methodResponses"][0][1].get("notDestroyed", {}):
				result["notDestroyed"].update(not_destroyed)

		return result

	def contact_card_changes(self, since_state: str) -> dict:
		"""Returns the changes in contact cards since the provided state."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:contacts"],
			method_calls=[
				[
					"ContactCard/changes",
					{
						"accountId": self.primary_account_id,
						"sinceState": since_state,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	# -------------------------------
	# Blob
	# -------------------------------

	def upload_blob(self, blob: bytes | str, content_type: str = "message/rfc822") -> dict:
		"""Uploads the blob data and returns a dictionary containing the response."""

		upload_url = self.upload_url.format(accountId=self.primary_account_id)
		response = self.__session.post(upload_url, data=blob, headers={"Content-Type": content_type})
		raise_for_status(response)

		return response.json()

	def upload_blobs_concurrently(self, blobs: list[tuple[bytes | str, str]]) -> list[dict]:
		"""Uploads multiple blobs concurrently and returns a list of dictionaries containing the responses."""

		if len(blobs) == 1:
			blob, content_type = blobs[0]
			return [self.upload_blob(blob, content_type)]

		results = []
		with ThreadPoolExecutor(max_workers=self.max_concurrent_upload) as executor:
			futures = {
				executor.submit(self.upload_blob, blob, content_type): (blob, content_type)
				for blob, content_type in blobs
			}
			for future in as_completed(futures):
				results.append(future.result())

		return results

	def download_blob(self, blob_id: str, name: str | None = None) -> bytes:
		"""Returns the blob data for the provided blob ID."""

		name = name or "blob"
		download_url = self.download_url.format(
			accountId=self.primary_account_id, blobId=blob_id, name=name, type="application/octet-stream"
		)
		response = self.__session.get(download_url)
		raise_for_status(response)

		return response.content

	def download_blobs_concurrently(self, blobs: list[tuple[str, str | None]]) -> dict[str, bytes]:
		"""Downloads multiple blobs concurrently and returns a dictionary containing the blob data."""

		if len(blobs) == 1:
			blob_id, name = blobs[0]
			return {blob_id: self.download_blob(blob_id, name)}

		results = {}
		with ThreadPoolExecutor(max_workers=5) as executor:
			futures = {executor.submit(self.download_blob, blob_id, name): blob_id for blob_id, name in blobs}
			for future in as_completed(futures):
				blob_id = futures[future]
				results[blob_id] = future.result()

		return results


def get_jmap_client(account: str, server: str | None = None, cache: bool = True) -> "JMAPClient":
	"""Returns a JMAP client for the given account."""

	def generator() -> "JMAPClient":
		account_doc = frappe.get_doc("Mail Account", account)
		account_cluster = get_cluster_for_tenant(account_doc.tenant)

		if not account_cluster:
			frappe.throw(_("No cluster found for the account {0}.").format(frappe.bold(account)))

		host = frappe.db.get_value("Mail Cluster", account_cluster, "base_url")

		if server:
			server_cluster, server_base_url = frappe.db.get_value(
				"Mail Server", server, ["cluster", "base_url"]
			)

			if server_cluster != account_cluster:
				frappe.throw(
					_("The server {0} does not belong to the same cluster as the account {1}.").format(
						frappe.bold(server), frappe.bold(account)
					)
				)

			host = server_base_url

		return JMAPClient(host, account_doc.email, account_doc._get_account_app_password())

	if cache and not server:
		return frappe.cache.hget("jmap:client", account, generator)
	else:
		return generator()


def invalidate_jmap_cache(account: str) -> None:
	"""Invalidates the JMAP cache for the given account."""

	invalidate_jmap_client_cache(account)
	invalidate_jmap_mailboxes_cache(account)
	invalidate_jmap_identities_cache(account)


def invalidate_jmap_client_cache(account: str) -> None:
	"""Invalidates the JMAP client cache for the given account."""

	frappe.cache.hdel("jmap:client", account)


def invalidate_jmap_mailboxes_cache(account: str) -> None:
	"""Invalidates the JMAP mailboxes cache for the given account."""

	frappe.cache.hdel("jmap:mailboxes", account)


def invalidate_jmap_identities_cache(account: str) -> None:
	"""Invalidates the JMAP identities cache for the given account."""

	frappe.cache.hdel("jmap:identities", account)


def get_mailboxes(account: str) -> list[dict]:
	"""Returns the mailboxes for the given account."""

	client = get_jmap_client(account)
	return client.mailboxes


def get_identities(account: str) -> list[dict]:
	"""Returns the identities for the given account."""

	client = get_jmap_client(account)
	return client.identities


def get_mailbox_id_by_role(account: str, role: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox ID for the given role."""

	client = get_jmap_client(account)
	return client.get_mailbox_id_by_role(role, raise_exception=raise_exception)


def get_mailbox_role_by_id(account: str, id: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox role for the given ID."""

	client = get_jmap_client(account)
	return client.get_mailbox_role_by_id(id, raise_exception=raise_exception)


def get_mailbox_name_by_id(account: str, id: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox name for the given ID."""

	client = get_jmap_client(account)
	return client.get_mailbox_name_by_id(id, raise_exception=raise_exception)


@frappe.whitelist()
def get_mailboxes_for_account(account: str) -> list[dict]:
	"""Returns the mailboxes for the given account."""

	has_permission_for_account(account)
	return get_mailboxes(account)


@frappe.whitelist()
def get_mailbox_id_for_account(account: str, role: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox ID for the given role."""

	has_permission_for_account(account)
	return get_mailbox_id_by_role(account, role, raise_exception=raise_exception)


@frappe.whitelist()
def get_mailbox_name_for_account(account: str, id: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox name for the given ID."""

	has_permission_for_account(account)
	return get_mailbox_name_by_id(account, id, raise_exception=raise_exception)


@frappe.whitelist()
def make_jmap_request(account: str, using: list[str], method_calls: list[list]) -> Any:
	"""Makes a JMAP request for the given account."""

	has_permission_for_account(account)
	client = get_jmap_client(account)
	return client._make_request(using, method_calls)


def raise_for_status(response: requests.Response) -> None:
	"""Raises an HTTPError if the response status code indicates an error."""

	if not response.ok:
		try:
			error_text = response.json()
		except Exception:
			error_text = response.text.strip()

		message = _("Error {0}: {1}").format(response.status_code, error_text)
		raise requests.exceptions.HTTPError(message, response=response)


def _get_name_map(full_name: str | None = None) -> dict:
	"""Returns the name map for the given full name."""

	if full_name:
		given, surname = full_name.split(" ", 1) if " " in full_name else (full_name, None)
		return {
			"full": full_name,
			"components": [{"kind": "given", "value": given}, {"kind": "surname", "value": surname}],
			"isOrdered": True,
		}

	return {}


def _get_emails_map(emails: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the emails map for the given emails dictionary."""

	if emails:
		counter = 0
		emails_map = {}
		for email in emails:
			emails_map[f"{counter}"] = {
				"address": email["address"],
				"label": email.get("label"),
				"contexts": {email["type"]: True},
			}
			counter += 1

		return emails_map


def _get_phones_map(phones: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the phones map for the given phones dictionary."""

	if phones:
		counter = 0
		phones_map = {}
		for phone in phones:
			phones_map[f"{counter}"] = {
				"number": phone["number"],
				"label": phone.get("label"),
				"contexts": {phone["type"]: True},
			}
			counter += 1

		return phones_map


def _get_addresses_map(addresses: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the addresses map for the given addresses dictionary."""

	if addresses:
		counter = 0
		addresses_map = {}
		for address in addresses:
			addresses_map[f"{counter}"] = {
				"street": {"components": [{"kind": "name", "value": address.get("street")}]},
				"locality": address.get("locality"),
				"region": address.get("region"),
				"postcode": address.get("postcode"),
				"country": address.get("country"),
				"contexts": {address["type"]: True},
			}
			counter += 1

		return addresses_map
