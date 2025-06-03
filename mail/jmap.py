from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import cached_property
from typing import Any
from urllib.parse import urljoin

import frappe
import requests
from frappe import _
from frappe.utils import create_batch

from mail.utils import batch_dict
from mail.utils.cache import get_cluster_for_tenant
from mail.utils.validation import validate_permission_for_account


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
		response.raise_for_status()
		self.__config = response.json()

	def _validate_capabilities(self, capabilities: list[str]) -> None:
		"""Validate the requested capabilities against the server's capabilities."""

		for capability in capabilities:
			if capability not in self.capabilities:
				raise ValueError(f"Unsupported capability: {capability}")

	def _validate_method_calls(self, method_calls: list[list]) -> None:
		"""Validate the method calls against the server's capabilities."""

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
		response = self.__session.post(self.api_url, headers=headers, json=payload)
		response.raise_for_status()

		return response.json()

	@property
	def capabilities(self) -> dict:
		"""Returns the capabilities of the JMAP server."""

		return self.__config["capabilities"]

	@property
	def max_objects_in_get(self) -> int:
		"""Returns the maximum number of objects in a single get request."""

		return self.capabilities["urn:ietf:params:jmap:core"]["maxObjectsInGet"]

	@property
	def max_objects_in_set(self) -> int:
		"""Returns the maximum number of objects in a single set request."""

		return self.capabilities["urn:ietf:params:jmap:core"]["maxObjectsInSet"]

	@property
	def accounts(self) -> dict:
		"""Returns the accounts for the logged-in user."""

		return self.__config["accounts"]

	@property
	def account_ids(self) -> list[str]:
		"""Returns the list of account IDs for the logged-in user."""

		return list(self.__config["accounts"].keys())

	@property
	def account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.primary_accounts["urn:ietf:params:jmap:mail"]

	@property
	def has_multiple_accounts(self) -> bool:
		"""Returns True if the user has multiple accounts, False otherwise."""

		return len(self.account_ids) > 1

	@property
	def primary_accounts(self) -> dict:
		"""Returns the primary accounts for the logged-in user."""

		return self.__config["primaryAccounts"]

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
	def max_concurrent_upload(self) -> int:
		"""Returns the maximum number of concurrent uploads supported by the JMAP server."""

		return self.capabilities["urn:ietf:params:jmap:core"].get("maxConcurrentUpload", 4)

	@cached_property
	def mailboxes(self) -> dict[list[dict]]:
		"""Returns the mailboxes for the logged-in user."""

		mailboxes = {}
		for account_id in [self.account_id]:
			response = self._make_request(
				["urn:ietf:params:jmap:mail"], [["Mailbox/get", {"accountId": account_id}, "0"]]
			)
			mailboxes[account_id] = response["methodResponses"][0][1]["list"]

		return mailboxes

	@cached_property
	def identities(self) -> list[dict]:
		"""Returns the identities for the logged-in user."""

		return self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[["Identity/get", {"accountId": self.account_id}, "0"]],
		)["methodResponses"][0][1]["list"]

	def get_mailboxes(self) -> list[dict]:
		"""Returns the mailboxes for the logged-in user."""

		mailboxes = []
		for mailbox in self.mailboxes[self.account_id]:
			mailboxes.append(
				{
					"id": mailbox["id"],
					"name": mailbox["name"],
					"role": mailbox["role"],
				}
			)

		if mailboxes:
			role_order = ["inbox", "sent", "drafts", "junk", "trash"]
			role_priority = {role: i for i, role in enumerate(role_order)}

			return sorted(mailboxes, key=lambda m: (role_priority.get(m["role"], len(role_order))))

		return mailboxes

	def get_mailbox_id(self, role: str | None = None, name: str | None = None) -> str | None:
		"""Returns the mailbox ID for the given role or name."""

		for mailbox in self.mailboxes[self.account_id]:
			if (role and mailbox.get("role").lower() == role.lower()) or (
				name and mailbox.get("name").lower() == name.lower()
			):
				return mailbox["id"]

	def get_mailbox_role(self, id: str) -> str | None:
		"""Returns the mailbox role for the given ID."""

		for mailbox in self.mailboxes[self.account_id]:
			if mailbox.get("id") == id:
				return mailbox["role"]

	def get_mailbox_name(self, id: str | None = None, role: str | None = None) -> str | None:
		"""Returns the mailbox name for the given ID or role."""

		for mailbox in self.mailboxes[self.account_id]:
			if (id and mailbox.get("id") == id) or (role and mailbox.get("role").lower() == role.lower()):
				return mailbox["name"]

	def email_query(self, filter: dict, position: int = 0, limit: int = 50) -> dict:
		"""Query emails based on the provided filter."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"Email/query",
					{
						"accountId": self.account_id,
						"filter": filter if filter else None,
						"position": position,
						"limit": limit,
						"sort": [{"property": "receivedAt", "isAscending": True}],
						"calculateTotal": True,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def thread_get(self, thread_ids: list[str]) -> dict[str, list]:
		"""Returns the threads for the provided thread IDs."""

		result = {}
		for ids_batch in create_batch(thread_ids, self.max_objects_in_get):
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Thread/get",
						{
							"accountId": self.account_id,
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

	def email_get(self, email_ids: list[str], properties: list[str] | None = None) -> tuple[list[dict], str]:
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
		for ids_batch in create_batch(email_ids, self.max_objects_in_get):
			response = self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Email/get",
						{
							"accountId": self.account_id,
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

	def email_changes(self, since_state: str) -> dict:
		"""Returns the changes in emails since the provided state."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"Email/changes",
					{
						"accountId": self.account_id,
						"sinceState": since_state,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]

	def download_blob(self, blob_id: str, name: str | None = None) -> bytes:
		"""Returns the blob data for the provided blob ID."""

		name = name or "blob"
		download_url = self.download_url.format(
			accountId=self.account_id, blobId=blob_id, name=name, type="application/octet-stream"
		)
		response = self.__session.get(download_url)
		response.raise_for_status()

		return response.content

	def upload_blob(self, blob: bytes | str, content_type: str = "message/rfc822") -> dict:
		"""Uploads the blob data and returns a dictionary containing the response."""

		upload_url = self.upload_url.format(accountId=self.account_id)
		response = self.__session.post(upload_url, data=blob, headers={"Content-Type": content_type})
		response.raise_for_status()

		return response.json()

	def upload_blobs_concurrently(self, blobs: list[tuple[bytes | str, str]]) -> list[dict]:
		"""Uploads multiple blobs concurrently and returns a list of dictionaries containing the responses."""

		upload_url = self.upload_url.format(accountId=self.account_id)

		def upload_single_blob(blob: tuple[bytes | str, str]) -> dict:
			content, content_type = blob
			response = self.__session.post(upload_url, data=content, headers={"Content-Type": content_type})
			response.raise_for_status()
			return response.json()

		results = []
		with ThreadPoolExecutor(max_workers=self.max_concurrent_upload) as executor:
			futures = {executor.submit(upload_single_blob, blob): blob for blob in blobs}
			for future in as_completed(futures):
				results.append(future.result())

		return results

	def email_set_keywords(self, email_id_keywords_map: dict[str, dict]) -> None:
		"""Update email keywords."""

		for map_batch in batch_dict(email_id_keywords_map, self.max_objects_in_set):
			self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Email/set",
						{
							"accountId": self.account_id,
							"update": {
								email_id: {"keywords": keywords} for email_id, keywords in map_batch.items()
							},
						},
						"0",
					]
				],
			)

	def email_set_mailbox(self, emails_to_move: list[tuple[str, str]], target_mailbox_id: str) -> None:
		"""Update emails mailbox."""

		update_data = {}
		junk_mailbox_id = self.get_mailbox_id(role="junk")
		trash_mailbox_id = self.get_mailbox_id(role="trash")

		for email in emails_to_move:
			email_id, from_mailbox_id = email

			update = {
				f"mailboxIds/{from_mailbox_id}": None,
				f"mailboxIds/{target_mailbox_id}": True,
			}

			is_to_junk = target_mailbox_id == junk_mailbox_id
			is_from_junk = from_mailbox_id == junk_mailbox_id
			is_to_trash = target_mailbox_id == trash_mailbox_id

			# !Junk -> Junk
			if is_to_junk and not is_from_junk:
				update.update(
					{
						"keywords/$notjunk": False,
						"keywords/$junk": True,
					}
				)
			# Junk -> Trash
			elif is_from_junk and is_to_trash:
				update.update(
					{
						"keywords/$notjunk": False,
						"keywords/$junk": True,
					}
				)
			# Junk -> !Junk
			elif is_from_junk and not is_to_junk:
				update.update(
					{
						"keywords/$junk": False,
						"keywords/$notjunk": True,
					}
				)

			update_data[email_id] = update

		for map_batch in batch_dict(update_data, self.max_objects_in_set):
			self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Email/set",
						{
							"accountId": self.account_id,
							"update": map_batch,
						},
						"0",
					]
				],
			)

	def email_set_destroy(self, email_ids: list[str]) -> None:
		"""Destroy emails."""

		for ids_batch in create_batch(email_ids, self.max_objects_in_set):
			self._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					[
						"Email/set",
						{
							"accountId": self.account_id,
							"destroy": ids_batch,
						},
						"0",
					]
				],
			)

	def push_subscription_get(self, subscription_ids: list[str] | None = None) -> list[dict]:
		"""Returns the push subscriptions for the provided subscription IDs."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"PushSubscription/get",
					{
						"ids": subscription_ids,
					},
					"0",
				]
			],
		)

		return response["methodResponses"][0][1]["list"]

	def push_subscription_create(
		self, unique_id: str, device_client_id: str, url: str, types: list[str] | None = None
	) -> dict:
		"""Creates a push subscription."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"PushSubscription/set",
					{
						"create": {
							unique_id: {
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

	def push_subscription_set_verification_code(
		self, subscription_id: str, verification_code: str
	) -> list[list]:
		"""Sets the verification code for a push subscription."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"PushSubscription/set",
					{
						"update": {subscription_id: {"verificationCode": verification_code}},
					},
					"0",
				],
				[
					"PushSubscription/get",
					{
						"ids": [subscription_id],
					},
					"1",
				],
			],
		)

		return response["methodResponses"]

	def push_subscription_set_expires(self, subscription_id: str, expires: str | None = None) -> list[list]:
		"""Sets the expiration date for a push subscription."""

		response = self._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"PushSubscription/set",
					{
						"update": {subscription_id: {"expires": expires}},
					},
					"0",
				],
				[
					"PushSubscription/get",
					{
						"ids": [subscription_id],
					},
					"1",
				],
			],
		)
		return response["methodResponses"]

	def push_subscription_set_destroy(self, subscription_ids: list[str]) -> None:
		"""Destroys push subscriptions."""

		for ids_batch in create_batch(subscription_ids, self.max_objects_in_set):
			self._make_request(
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

		return JMAPClient(host, account_doc.email, account_doc.get_password())

	if cache:
		cache_key = "jmap:client"
		if server:
			cache_key = f"{cache_key}:{server}"

		return frappe.cache.hget(cache_key, account, generator)
	else:
		return generator()


def invalidate_jmap_client_cache(account: str) -> None:
	"""Invalidates the JMAP client cache for the given account."""

	frappe.cache.hdel("jmap:client", account)


def get_mailboxes(account: str) -> list[dict]:
	"""Returns the mailboxes for the given account."""

	client = get_jmap_client(account)
	return client.get_mailboxes()


def get_identities(account: str) -> list[dict]:
	"""Returns the identities for the given account."""

	client = get_jmap_client(account)
	return client.identities


def get_mailbox_id(account: str, role: str | None = None, name: str | None = None) -> str | None:
	"""Returns the mailbox ID for the given role or name."""

	client = get_jmap_client(account)
	return client.get_mailbox_id(role, name)


def get_mailbox_role(account: str, id: str) -> str | None:
	"""Returns the mailbox role for the given ID."""

	client = get_jmap_client(account)
	return client.get_mailbox_role(id)


def get_mailbox_name(account: str, id: str | None = None, role: str | None = None) -> str | None:
	"""Returns the mailbox name for the given ID or role."""

	client = get_jmap_client(account)
	return client.get_mailbox_name(id, role)


@frappe.whitelist()
def get_mailboxes_for_account(account: str) -> list[dict]:
	"""Returns the mailboxes for the given account."""

	validate_permission_for_account(account)
	return get_mailboxes(account)


@frappe.whitelist()
def get_mailbox_id_for_account(account: str, role: str | None = None, name: str | None = None) -> str | None:
	"""Returns the mailbox ID for the given role or name."""

	validate_permission_for_account(account)
	return get_mailbox_id(account, role, name)


@frappe.whitelist()
def get_mailbox_name_for_account(account: str, id: str | None = None, role: str | None = None) -> str | None:
	"""Returns the mailbox name for the given ID or role."""

	validate_permission_for_account(account)
	return get_mailbox_name(account, id, role)
