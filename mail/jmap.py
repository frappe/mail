import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import cached_property
from typing import Any, Literal
from urllib.parse import urljoin
from uuid import uuid7

import frappe
import requests
from frappe import _
from frappe.utils import create_batch

from mail import __version__
from mail.utils.dt import convert_to_utc, utcnow
from mail.utils.user import has_role
from mail.utils.validation import has_permission_for_user


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

		return self.capabilities["urn:ietf:params:jmap:core"].get("maxSizeUpload") or 50_000_000

	@property
	def max_concurrent_upload(self) -> int:
		"""Returns the maximum number of concurrent uploads supported by the JMAP server."""

		return self.capabilities["urn:ietf:params:jmap:core"].get("maxConcurrentUpload") or 4

	@property
	def max_size_request(self) -> int:
		"""Returns the maximum size of a request supported by the JMAP server."""

		return self.capabilities["urn:ietf:params:jmap:core"].get("maxSizeRequest") or 10_000_000

	@property
	def max_concurrent_requests(self) -> int:
		"""Returns the maximum number of concurrent requests supported by the JMAP server."""

		return self.capabilities["urn:ietf:params:jmap:core"].get("maxConcurrentRequests") or 4

	@property
	def max_calls_in_request(self) -> int:
		"""Returns the maximum number of calls in a single request."""

		return self.capabilities["urn:ietf:params:jmap:core"].get("maxCallsInRequest") or 16

	@property
	def max_objects_in_get(self) -> int:
		"""Returns the maximum number of objects in a single get request."""

		return self.capabilities["urn:ietf:params:jmap:core"].get("maxObjectsInGet") or 500

	@property
	def max_objects_in_set(self) -> int:
		"""Returns the maximum number of objects in a single set request."""

		return self.capabilities["urn:ietf:params:jmap:core"].get("maxObjectsInSet") or 500

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
			mailboxes = frappe.db.get_all("Mailbox", {"user": self.__session.auth[0]})
			return [
				{
					"id": mailbox["id"],
					"name": mailbox["name"],
					"role": mailbox["role"],
					"_name": mailbox["_name"],
					"_parent": mailbox["_parent"],
					"parent_id": mailbox["parent_id"],
					"subscribed": mailbox["subscribed"],
				}
				for mailbox in mailboxes
			]

		return frappe.cache.hget("jmap:mailboxes", self.__session.auth[0], generator)

	@property
	def identities(self) -> list[dict]:
		"""Returns the identities for the logged-in user."""

		def generator() -> list[dict]:
			identities = frappe.db.get_all("Identity", {"user": self.__session.auth[0]})
			return identities

		return frappe.cache.hget("jmap:identities", self.__session.auth[0], generator)

	@cached_property
	def address_books(self) -> list[dict]:
		"""Returns the address books for the logged-in user."""

		address_books = frappe.db.get_all("Address Book", {"user": self.__session.auth[0]})
		return address_books

	@cached_property
	def calendars(self) -> list[dict]:
		"""Returns the calendars for the logged-in user."""

		calendars = frappe.db.get_all("Calendar", {"user": self.__session.auth[0]})
		return calendars

	@cached_property
	def participant_identities(self) -> list[dict]:
		"""Returns the participant identities for the logged-in user."""

		identities = frappe.db.get_all("Participant Identity", {"user": self.__session.auth[0]})
		return identities

	# -------------------------------
	# Identity
	# -------------------------------

	def identity_create(
		self,
		creation_id: str,
		email: str,
		name: str | None = None,
		reply_to: list[dict] | None = None,
		bcc: list[dict] | None = None,
		text_signature: str | None = None,
		html_signature: str | None = None,
	) -> dict:
		"""Creates a identity with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"Identity/set",
					{
						"accountId": self.primary_account_id,
						"create": {
							creation_id: {
								"email": email,
								"name": name or "",
								"replyTo": reply_to or [],
								"bcc": bcc or [],
								"textSignature": text_signature or "",
								"htmlSignature": html_signature or "",
							}
						},
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def identity_get(self, ids: list[str] | None = None) -> list[dict]:
		"""Returns the identities for the provided identity IDs."""

		def fetch(ids_batch: list[str] | None) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Identity/get",
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
			identities = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				identities.extend(fetch(ids_batch))
			return identities

		return fetch(ids)

	def identity_update(
		self,
		id: str,
		name: str | None = None,
		reply_to: list[dict] | None = None,
		bcc: list[dict] | None = None,
		text_signature: str | None = None,
		html_signature: str | None = None,
	) -> dict:
		"""Updates the identity with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"Identity/set",
					{
						"accountId": self.primary_account_id,
						"update": {
							id: {
								"name": name or "",
								"replyTo": reply_to or [],
								"bcc": bcc or [],
								"textSignature": text_signature or "",
								"htmlSignature": html_signature or "",
							}
						},
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def identity_delete(self, ids: list[str]) -> dict:
		"""Destroys the identities with the given IDs."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Identity/set",
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

	def get_identity_id_by_email(self, email: str, raise_exception: bool = False) -> str | None:
		"""Returns the identity ID for the given email."""

		for identity in self.identities:
			if identity["email"].lower() == email.lower():
				return identity["id"]

		if raise_exception:
			frappe.throw(
				_("Identity with email {0} not found for user {1}.").format(
					frappe.bold(email), frappe.bold(self.__session.auth[0])
				)
			)

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

	def get_mailbox_id_by_role(
		self, role: str, create_if_not_exists: bool = False, raise_exception: bool = False
	) -> str | None:
		"""Return the mailbox ID for a given role, optionally creating it if missing."""

		def find_id(role: str) -> str | None:
			role = role.lower()
			for mailbox in self.mailboxes:
				mailbox_role = (mailbox.get("role") or "").lower()
				if mailbox_role == role:
					return mailbox.get("id")
			return None

		if mailbox_id := find_id(role):
			return mailbox_id

		if not create_if_not_exists:
			if raise_exception:
				frappe.throw(
					_("Mailbox with role {0} not found for user {1}.").format(
						frappe.bold(role), frappe.bold(self.__session.auth[0])
					)
				)
			return None

		creation_id = str(uuid7())
		response = self.mailbox_create(creation_id, role.title(), role, subscribed=True)

		if response.get("notCreated"):
			if raise_exception:
				frappe.throw(
					_(response["notCreated"][creation_id]["description"]), title=_("Mailbox Creation Error")
				)
			return None

		invalidate_jmap_mailboxes_cache(self.__session.auth[0])
		return find_id(role)

	def get_mailbox_role_by_id(self, id: str, raise_exception: bool = False) -> str | None:
		"""Returns the mailbox role for the given ID."""

		for mailbox in self.mailboxes:
			if mailbox["id"] == id:
				return mailbox["role"]

		if raise_exception:
			frappe.throw(
				_("Mailbox with ID {0} not found for user {1}.").format(
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
				_("Mailbox with ID {0} not found for user {1}.").format(
					frappe.bold(id), frappe.bold(self.__session.auth[0])
				)
			)

		# -------------------------------

	# -------------------------------
	# Quota
	# -------------------------------

	def quota_query(
		self, filter: dict | None = None, position: int = 0, limit: int = 50, sort: list[dict] | None = None
	) -> dict:
		"""Query quotas in batches until reaching the limit."""

		ids = []
		total = None
		batch_size = min(limit, self.max_objects_in_get)

		while len(ids) < limit:
			response = self._make_request(
				using=["urn:ietf:params:jmap:quota"],
				method_calls=[
					[
						"Quota/query",
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

	def quota_get(self, ids: list[str] | None = None) -> list[dict]:
		"""Returns the quotas for the provided quota IDs."""

		def fetch(ids_batch: list[str] | None) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:quota"],
				method_calls=[
					[
						"Quota/get",
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
			quotas = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				quotas.extend(fetch(ids_batch))
			return quotas

		return fetch(ids)

	def quota_changes(self, since_state: str) -> dict:
		"""Returns the changes in quota since the provided state."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:quota"],
			method_calls=[
				[
					"Quota/changes",
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

		identity_id = self.get_identity_id_by_email(from_email, raise_exception=True)
		draft_mailbox_id = self.get_mailbox_id_by_role(
			"drafts", create_if_not_exists=True, raise_exception=True
		)
		sent_mailbox_id = self.get_mailbox_id_by_role(
			"sent", create_if_not_exists=not save_as_draft, raise_exception=not save_as_draft
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
	# Address Book
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

	# -------------------------------
	# Contact Card
	# -------------------------------

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

		timestamp = utcnow()
		response = self._make_request(
			using=["urn:ietf:params:jmap:contacts"],
			method_calls=[
				[
					"ContactCard/set",
					{
						"accountId": self.primary_account_id,
						"create": {
							creation_id: {
								"@type": "Card",
								"version": "1.0",
								"kind": kind,
								"name": _get_name_map(full_name),
								"emails": _get_emails_map(emails),
								"phones": _get_phones_map(phones),
								"addresses": _get_addresses_map(addresses),
								"addressBookIds": {id: True for id in address_book_ids},
								"created": timestamp,
								"updated": timestamp,
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

	def contact_card_update_address_books(
		self,
		ids: list[str],
		add_address_book_id: str | None = None,
		remove_address_book_id: str | None = None,
		move_to_address_book_id: str | None = None,
	) -> dict:
		"""
		Updates addressBookIds for the provided contact cards.

		Behavior:
		- add_address_book_id: adds the contact to an address book
		- remove_address_book_id: removes the contact from an address book
		- add + remove: moves contact between address books (patch-based)
		- move_to_address_book_id: replaces addressBookIds entirely
		"""

		if move_to_address_book_id and (add_address_book_id or remove_address_book_id):
			frappe.throw(
				_("{0} cannot be combined with add/remove operations.").format("move_to_address_book_id")
			)

		if not any([add_address_book_id, remove_address_book_id, move_to_address_book_id]):
			frappe.throw(_("At least one address book operation must be provided."))

		result = {"updated": [], "notUpdated": {}}

		for ids_batch in create_batch(ids, self.max_objects_in_set):
			if move_to_address_book_id:
				# Full replacement of addressBookIds
				update_payload = {"addressBookIds": {move_to_address_book_id: True}, "updated": utcnow()}
			else:
				# Patch-based update of addressBookIds
				update_payload = {"updated": utcnow()}

				if add_address_book_id:
					update_payload[f"addressBookIds/{add_address_book_id}"] = True
				if remove_address_book_id:
					update_payload[f"addressBookIds/{remove_address_book_id}"] = None

			response = self._make_request(
				using=["urn:ietf:params:jmap:contacts"],
				method_calls=[
					[
						"ContactCard/set",
						{
							"accountId": self.primary_account_id,
							"update": {id: update_payload for id in ids_batch},
						},
						"0",
					]
				],
			)

			result["updated"].extend(response["methodResponses"][0][1].get("updated", []))
			if not_updated := response["methodResponses"][0][1].get("notUpdated", {}):
				result["notUpdated"].update(not_updated)

		return result

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
	# Calendar
	# -------------------------------

	def calendar_create(
		self,
		creation_id: str,
		name: str,
		color: str | None = None,
		description: str | None = None,
		sort_order: int = 0,
		include_in_availability: Literal["all", "attending", "none"] = "all",
		time_zone: str | None = None,
		subscribed: bool = True,
		visible: bool = True,
		default: bool = False,
	) -> dict:
		"""Creates a calendar book with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"Calendar/set",
					{
						"accountId": self.primary_account_id,
						"create": {
							creation_id: {
								"name": name,
								"color": color or None,
								"description": description or None,
								"sortOrder": sort_order or 0,
								"includeInAvailability": include_in_availability,
								"timeZone": time_zone or None,
								"isSubscribed": subscribed or False,
								"isVisible": visible or True,
							}
						},
						"onSuccessSetIsDefault": f"#{creation_id}" if default else None,
					},
					"0",
				]
			],
		)
		return response["methodResponses"][0][1]

	def calendar_get(self, ids: list[str] | None = None) -> list[dict]:
		"""Returns the calendars for the provided calendar IDs."""

		def fetch(ids_batch: list[str] | None) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"Calendar/get",
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
			calendars = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				calendars.extend(fetch(ids_batch))
			return calendars

		return fetch(ids)

	def calendar_update(
		self,
		id: str,
		name: str,
		color: str | None = None,
		description: str | None = None,
		sort_order: int = 0,
		include_in_availability: Literal["all", "attending", "none"] = "all",
		time_zone: str | None = None,
		subscribed: bool = True,
		visible: bool = True,
		default: bool = False,
	) -> dict:
		"""Updates the calendar with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"Calendar/set",
					{
						"accountId": self.primary_account_id,
						"update": {
							id: {
								"name": name,
								"color": color or None,
								"description": description or None,
								"sortOrder": sort_order or 0,
								"includeInAvailability": include_in_availability,
								"timeZone": time_zone or None,
								"isSubscribed": subscribed or False,
								"isVisible": visible or False,
							}
						},
						"onSuccessSetIsDefault": id if default else None,
					},
					"0",
				]
			],
		)
		return response["methodResponses"][0][1]

	def calendar_delete(self, ids: list[str], remove_events: bool = False) -> dict:
		"""Destroys the calendars with the given IDs."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"Calendar/set",
						{
							"accountId": self.primary_account_id,
							"destroy": ids_batch,
							"onDestroyRemoveEvents": remove_events,
						},
						"0",
					]
				],
			)

			result["destroyed"].extend(response["methodResponses"][0][1].get("destroyed", []))
			if not_destroyed := response["methodResponses"][0][1].get("notDestroyed", {}):
				result["notDestroyed"].update(not_destroyed)

		return result

	def calendar_changes(self, since_state: str) -> dict:
		"""Returns the changes in calendars since the provided state."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"Calendar/changes",
					{
						"accountId": self.primary_account_id,
						"sinceState": since_state,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def get_default_calendar_id(self, raise_exception: bool = False) -> str | None:
		"""Returns the default calendar ID for the primary account."""

		for calendar in self.calendars:
			if calendar.get("default"):
				return calendar["id"]

		if raise_exception:
			frappe.throw(_("No default calendar found for the account."))

	# -------------------------------
	# Event
	# -------------------------------

	def calendar_event_create(
		self,
		creation_id: str,
		uid: str,
		organizer: str | None = None,
		calendar_ids: list[str] | None = None,
		status: Literal["tentative", "confirmed", "cancelled"] = "confirmed",
		draft: bool = False,
		title: str | None = None,
		start: str | None = None,
		duration: str | None = None,
		time_zone: str | None = None,
		recurrence_rule: dict | None = None,
		show_without_time: bool = False,
		privacy: str | None = None,
		free_busy_status: str | None = None,
		description: str | None = None,
		locations: list[dict] | None = None,
		links: list[dict] | None = None,
		participants: list[dict] | None = None,
		alerts: list[dict] | None = None,
		use_default_alerts: bool = False,
		send_scheduling_messages: bool = False,
	) -> dict:
		"""Creates a calendar event with the given parameters."""

		if organizer:
			self.has_participant_identity_for_email(organizer, raise_exception=True)
		else:
			organizer = self.get_default_participant_identity(raise_exception=True)

		if not calendar_ids:
			calendar_ids = [self.get_default_calendar_id(raise_exception=True)]

		timestamp = utcnow()
		organizer = organizer.lower()
		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"CalendarEvent/set",
					{
						"accountId": self.primary_account_id,
						"create": {
							creation_id: {
								"@type": "Event",
								"uid": uid,
								"organizerCalendarAddress": organizer or None,
								"calendarIds": {id: True for id in calendar_ids},
								"status": status or None,
								"isDraft": draft or False,
								"title": title or None,
								"start": start or None,
								"duration": duration or None,
								"timeZone": time_zone or None,
								"recurrenceRule": recurrence_rule or None,
								"showWithoutTime": show_without_time or False,
								"privacy": privacy or None,
								"freeBusyStatus": free_busy_status or None,
								"description": description or None,
								"locations": _get_locations_map(locations),
								"links": _get_links_map(links),
								"participants": _get_participants_map(organizer, participants),
								"alerts": _get_alerts_map(alerts),
								"useDefaultAlerts": use_default_alerts or False,
								"created": timestamp,
								"updated": timestamp,
							}
						},
						"sendSchedulingMessages": send_scheduling_messages or False,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def calendar_event_query(
		self,
		filter: dict | None = None,
		position: int = 0,
		limit: int = 50,
		sort: list[dict] | None = None,
		time_zone: str | None = None,
		expand_recurrences: bool = False,
	) -> dict:
		"""Query calendar events in batches until reaching the limit."""

		ids = []
		total = None
		batch_size = min(limit, self.max_objects_in_get)
		sort = sort or [{"property": "start", "isAscending": True}]

		while len(ids) < limit:
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"CalendarEvent/query",
						{
							"accountId": self.primary_account_id,
							"filter": filter or {},
							"position": position,
							"limit": batch_size,
							"sort": sort or [],
							"timeZone": time_zone or None,
							"expandRecurrences": expand_recurrences,
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

	def calendar_event_get(self, ids: list[str] | None = None) -> list[dict]:
		"""Returns the calendar events for the provided calendar event IDs."""

		def fetch(ids_batch: list[str] | None) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"CalendarEvent/get",
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
			calendar_events = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				calendar_events.extend(fetch(ids_batch))
			return calendar_events

		return fetch(ids)

	def calendar_event_update(self) -> dict:
		pass

	def calendar_event_delete(self, ids: list[str]) -> dict:
		"""Destroys the calendar events with the given IDs."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"CalendarEvent/set",
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

	def calendar_event_changes(self, since_state: str) -> dict:
		"""Returns the changes in calendar events since the provided state."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"CalendarEvent/changes",
					{
						"accountId": self.primary_account_id,
						"sinceState": since_state,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def calendar_event_parse(self, blob_ids: list[str]) -> dict:
		"""Parses calendar events from the provided blob IDs."""

		result = {"parsed": {}, "notFound": {}, "notParsable": {}}
		for blob_ids_batch in create_batch(blob_ids, self.max_objects_in_get):
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"CalendarEvent/parse",
						{
							"accountId": self.primary_account_id,
							"blobIds": blob_ids_batch,
						},
						"0",
					]
				],
			)

			result["parsed"].update(response["methodResponses"][0][1].get("parsed", {}))
			if not_found := response["methodResponses"][0][1].get("notFound", {}):
				result["notFound"].update(not_found)
			if not_parsable := response["methodResponses"][0][1].get("notParsable", {}):
				result["notParsable"].update(not_parsable)

		return result

	# -------------------------------
	# Participant Identity
	# -------------------------------

	def participant_identity_create(
		self,
		creation_id: str,
		name: str,
		email: str,
		default: bool = False,
	) -> dict:
		"""Creates a participant identity with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"ParticipantIdentity/set",
					{
						"accountId": self.primary_account_id,
						"create": {
							creation_id: {
								"name": name,
								"calendarAddress": f"mailto:{email}",
							}
						},
						"onSuccessSetIsDefault": f"#{creation_id}" if default else None,
					},
					"0",
				]
			],
		)
		return response["methodResponses"][0][1]

	def participant_identity_get(self, ids: list[str] | None = None) -> list[dict]:
		"""Returns the participant identities for the provided participant identity IDs."""

		def fetch(ids_batch: list[str] | None) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"ParticipantIdentity/get",
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
			participant_identities = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				participant_identities.extend(fetch(ids_batch))
			return participant_identities

		return fetch(ids)

	def participant_identity_update(
		self,
		id: str,
		name: str,
		email: str,
		default: bool = False,
	) -> dict:
		"""Updates the participant identity with the given parameters."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"ParticipantIdentity/set",
					{
						"accountId": self.primary_account_id,
						"update": {
							id: {
								"name": name,
								"calendarAddress": f"mailto:{email}",
							}
						},
						"onSuccessSetIsDefault": id if default else None,
					},
					"0",
				]
			],
		)
		return response["methodResponses"][0][1]

	def participant_identity_delete(self, ids: list[str]) -> dict:
		"""Destroys the participant identities with the given IDs."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"ParticipantIdentity/set",
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

	def participant_identity_changes(self, since_state: str) -> dict:
		"""Returns the changes in participant identities since the provided state."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"ParticipantIdentity/changes",
					{
						"accountId": self.primary_account_id,
						"sinceState": since_state,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def has_participant_identity_for_email(self, email: str, raise_exception: bool = False) -> bool:
		"""Checks if a participant identity exists for the given email."""

		for identity in self.identities:
			if identity["email"].lower() == email.lower():
				return True

		if raise_exception:
			frappe.throw(_("No participant identity found for email: {0}").format(email))

		return False

	def get_default_participant_identity(self, raise_exception: bool = False) -> str | None:
		"""Returns the email of the default participant identity."""

		for identity in self.participant_identities:
			if identity.get("default", False):
				return identity["email"].lower()

		if raise_exception:
			frappe.throw(_("No default participant identity found."))

	# -------------------------------
	# Principal
	# -------------------------------

	def principal_get_availability(
		self,
		utc_start: str,
		utc_end: str,
		show_details: bool = False,
		event_properties: list[str] | None = None,
		id: str | None = None,
	) -> dict:
		"""Returns the availability information for the provided principal ID."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"Principal/getAvailability",
					{
						"accountId": self.primary_account_id,
						"id": id or self.primary_account_id,
						"start": utc_start,
						"end": utc_end,
						"showDetails": show_details,
						"eventProperties": event_properties or None,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	# -------------------------------
	# Calendar Event Notification
	# -------------------------------

	def calendar_event_notification_query(
		self, filter: dict | None = None, position: int = 0, limit: int = 50, sort: list[dict] | None = None
	) -> dict:
		"""Query calendar event notifications in batches until reaching the limit."""

		ids = []
		total = None
		batch_size = min(limit, self.max_objects_in_get)
		sort = sort or [{"property": "created", "isAscending": True}]

		while len(ids) < limit:
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"CalendarEventNotification/query",
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

	def calendar_event_notification_get(self, ids: list[str] | None = None) -> list[dict]:
		"""Returns the calendar event notifications for the provided notification IDs."""

		def fetch(ids_batch: list[str] | None) -> list[dict]:
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"CalendarEventNotification/get",
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
			notifications = []
			for ids_batch in create_batch(ids, self.max_objects_in_get):
				notifications.extend(fetch(ids_batch))
			return notifications

		return fetch(ids)

	def calendar_event_notification_delete(self, ids: list[str]) -> dict:
		"""Destroys the calendar event notifications with the given IDs."""

		result = {"destroyed": [], "notDestroyed": {}}
		for ids_batch in create_batch(ids, self.max_objects_in_set):
			response = self._make_request(
				using=["urn:ietf:params:jmap:calendars"],
				method_calls=[
					[
						"CalendarEventNotification/set",
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

	def calendar_event_notification_changes(self, since_state: str) -> dict:
		"""Returns the changes in calendar event notifications since the provided state."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:calendars"],
			method_calls=[
				[
					"CalendarEventNotification/changes",
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
		"""Uploads multiple blobs concurrently and returns responses in input order."""

		count = len(blobs)
		if count == 0:
			return []

		results = [None] * count

		if count == 1:
			blob, content_type = blobs[0]
			return [self.upload_blob(blob, content_type)]

		with ThreadPoolExecutor(max_workers=self.max_concurrent_upload) as executor:
			future_to_index = {}

			for index, (blob, content_type) in enumerate(blobs):
				future = executor.submit(self.upload_blob, blob, content_type)
				future_to_index[future] = index

			for future in as_completed(future_to_index):
				index = future_to_index[future]
				results[index] = future.result()

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


def get_jmap_client(user: str, ignore_permissions: bool = False, cache: bool = True) -> "JMAPClient":
	"""Returns a JMAP client for the given user."""

	def generator() -> "JMAPClient":
		user_doc = frappe.get_doc("User", user)

		if not user_doc.jmap_server_url or not user_doc.jmap_username or not user_doc.jmap_app_password:
			frappe.throw(
				_("JMAP settings are not configured for user {0}.").format(frappe.bold(user)),
				frappe.ValidationError,
			)

		if frappe.db.get_value("Mail Tenant Member", {"user": user}, "tenant"):
			if user_doc.name != user_doc.jmap_username:
				frappe.throw(
					_(
						"JMAP username for tenant-bound user {0} must be the same as the system username."
					).format(frappe.bold(user)),
					frappe.ValidationError,
				)

		return JMAPClient(
			user_doc.jmap_server_url, user_doc.jmap_username, user_doc.get_password("jmap_app_password")
		)

	if not ignore_permissions:
		if not has_permission_for_user(user, raise_exception=False):
			frappe.throw(
				_("You do not have permission to access the JMAP client for user {0}.").format(
					frappe.bold(user)
				),
				frappe.PermissionError,
			)

	if not bool(frappe.db.get_value("User", user, "enabled")):
		frappe.throw(_("User {0} is disabled.").format(frappe.bold(user)))

	if not has_role(user, ["Mail User"]):
		frappe.throw(_("User {0} does not have the Mail User role.").format(frappe.bold(user)))

	if cache:
		return frappe.cache.hget("jmap:client", user, generator)
	else:
		return generator()


def invalidate_jmap_cache(user: str) -> None:
	"""Invalidates the JMAP cache for the given user."""

	invalidate_jmap_client_cache(user)
	invalidate_jmap_mailboxes_cache(user)
	invalidate_jmap_identities_cache(user)


def invalidate_jmap_client_cache(user: str) -> None:
	"""Invalidates the JMAP client cache for the given user."""

	frappe.cache.hdel("jmap:client", user)


def invalidate_jmap_mailboxes_cache(user: str) -> None:
	"""Invalidates the JMAP mailboxes cache for the given user."""

	frappe.cache.hdel("jmap:mailboxes", user)


def invalidate_jmap_identities_cache(user: str) -> None:
	"""Invalidates the JMAP identities cache for the given user."""

	frappe.cache.hdel("jmap:identities", user)
	frappe.cache.hdel(f"user|{user}", "emails")


def get_identities(user: str) -> list[dict]:
	"""Returns the identities for the given user."""

	client = get_jmap_client(user)
	return client.identities


def get_identity_id_by_email(user: str, email: str, raise_exception: bool = False) -> str | None:
	"""Returns the identity ID for the given email."""

	client = get_jmap_client(user)
	return client.get_identity_id_by_email(email, raise_exception=raise_exception)


def get_mailboxes(user: str) -> list[dict]:
	"""Returns the mailboxes for the given user."""

	client = get_jmap_client(user)
	return client.mailboxes


def get_mailbox_id_by_role(
	user: str, role: str, create_if_not_exists: bool = False, raise_exception: bool = False
) -> str | None:
	"""Returns the mailbox ID for the given role."""

	client = get_jmap_client(user)
	return client.get_mailbox_id_by_role(
		role, create_if_not_exists=create_if_not_exists, raise_exception=raise_exception
	)


def get_mailbox_role_by_id(user: str, id: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox role for the given ID."""

	client = get_jmap_client(user)
	return client.get_mailbox_role_by_id(id, raise_exception=raise_exception)


def get_mailbox_name_by_id(user: str, id: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox name for the given ID."""

	client = get_jmap_client(user)
	return client.get_mailbox_name_by_id(id, raise_exception=raise_exception)


@frappe.whitelist()
def get_mailboxes_for_user(user: str) -> list[dict]:
	"""Returns the mailboxes for the given user."""

	has_permission_for_user(user)
	return get_mailboxes(user)


@frappe.whitelist()
def get_mailbox_id_for_user(
	user: str, role: str, create_if_not_exists: bool = False, raise_exception: bool = False
) -> str | None:
	"""Returns the mailbox ID for the given role."""

	has_permission_for_user(user)
	return get_mailbox_id_by_role(
		user, role, create_if_not_exists=create_if_not_exists, raise_exception=raise_exception
	)


@frappe.whitelist()
def get_mailbox_name_for_user(user: str, id: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox name for the given ID."""

	has_permission_for_user(user)
	return get_mailbox_name_by_id(user, id, raise_exception=raise_exception)


@frappe.whitelist()
def make_jmap_request(user: str, using: list[str], method_calls: list[list]) -> Any:
	"""Makes a JMAP request for the given user."""

	has_permission_for_user(user)
	client = get_jmap_client(user)
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
			"@type": "Name",
			"full": full_name,
			"components": [{"kind": "given", "value": given}, {"kind": "surname", "value": surname}],
			"isOrdered": True,
		}

	return {}


def _get_emails_map(emails: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the emails map for the given emails dictionary."""

	if emails:
		emails_map = {}
		for email in emails:
			emails_map[str(uuid7())] = {
				"address": email["address"],
				"label": email.get("label"),
				"contexts": {email["type"]: True},
			}

		return emails_map


def _get_phones_map(phones: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the phones map for the given phones dictionary."""

	if phones:
		phones_map = {}
		for phone in phones:
			phones_map[str(uuid7())] = {
				"number": phone["number"],
				"label": phone.get("label"),
				"contexts": {phone["type"]: True},
			}

		return phones_map


def _get_addresses_map(addresses: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the addresses map for the given addresses dictionary."""

	if addresses:
		addresses_map = {}
		for address in addresses:
			addresses_map[str(uuid7())] = {
				"street": {"components": [{"kind": "name", "value": address.get("street")}]},
				"locality": address.get("locality"),
				"region": address.get("region"),
				"postcode": address.get("postcode"),
				"country": address.get("country"),
				"contexts": {address["type"]: True},
			}

		return addresses_map


def _get_locations_map(locations: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the locations map for the given locations dictionary."""

	if locations:
		locations_map = {}
		for location in locations:
			uid = location.get("uid") or str(uuid7())
			locations_map[uid] = {
				"@type": "Location",
				"name": location.get("name"),
			}

		return locations_map


def _get_links_map(links: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the links map for the given links dictionary."""

	if links:
		links_map = {}
		for link in links:
			uid = link.get("uid") or str(uuid7())
			links_map[uid] = {
				"@type": "Link",
				"href": link.get("href"),
				"contentType": link.get("content_type"),
			}

		return links_map


def _get_alerts_map(alerts: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the alerts map for the given alerts dictionary."""

	if alerts:
		alerts_map = {}
		for alert in alerts:
			if alert["type"] == "OffsetTrigger":
				trigger = {
					"@type": "OffsetTrigger",
					"relativeTo": alert["relative_to"].lower(),
					"offset": alert["offset"].upper(),
				}
			elif alert["type"] == "AbsoluteTrigger":
				trigger = {
					"@type": "AbsoluteTrigger",
					"when": alert["when"].upper(),
				}
			else:
				continue

			uid = alert.get("uid") or str(uuid7())
			alerts_map[uid] = {
				"@type": "Alert",
				"action": alert["action"].lower(),
				"trigger": trigger,
			}

		return alerts_map


def _get_participants_map(organizer: str, participants: list[dict] | None = None) -> dict[str, dict] | None:
	"""Returns the participants map for the given participants dictionary."""

	if participants:
		participants_map = {}
		participants_emails = []
		for participant in participants:
			email = participant["email"].lower()
			if email == organizer or email in participants_emails:
				continue

			uid = participant.get("uid") or str(uuid7())
			expect_reply = participant.get("expect_reply", False)
			calendar_address = f"mailto:{email}" if email else None

			if expect_reply:
				send_to = (
					participant.get("send_to") or {"imip": calendar_address} if calendar_address else None
				)
				schedule_id = participant.get("schedule_id") or calendar_address
			else:
				send_to = None
				schedule_id = None

			participants_map[uid] = {
				"@type": "Participant",
				"name": participant.get("name") or None,
				"sendTo": send_to,
				"scheduleId": schedule_id,
				"calendarAddress": calendar_address,
				"kind": participant.get("kind", "").lower() or None,
				"description": participant.get("description") or None,
				"roles": participant.get("roles") or None,
				"participationStatus": participant.get("participation_status", "").lower() or None,
				"expectReply": expect_reply,
			}
			participants_emails.append(email)

		return participants_map
