# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

from mail.backend import get_mail_backend_api
from mail.utils import extract_filter_values, rename_keys


class MessageQueue(Document):
	def db_insert(self, *args, **kwargs) -> None:
		raise NotImplementedError

	def load_from_db(self) -> "MessageQueue":
		message = fetch_message_details(self.name)
		return super(Document, self).__init__(message)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		cancel_message(self.name)

		if not frappe.flags.in_bulk_delete:
			frappe.msgprint(_("Message deleted successfully."), alert=True)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = filters or []
		cluster, text = extract_filter_values(filters, [{"cluster": "="}, {"text": "like"}])

		if cluster:
			messages = fetch_messages(cluster, limit=page_length, text=text)
			if not messages:
				frappe.msgprint(_("No messages found."), alert=True)

			return messages

		frappe.msgprint(_("Please select a cluster to view messages."), alert=True)
		return []

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = filters or []
		cluster, text = extract_filter_values(filters, [{"cluster": "="}, {"text": "like"}])

		return frappe.cache.get_value(get_total_cache_key(cluster, text)) if cluster else 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	@frappe.whitelist()
	def retry_delivery(self) -> None:
		"""Retries delivery of a message to all recipients."""

		frappe.only_for("System Manager")
		retry_message(self.name)
		frappe.msgprint(_("Delivery retried successfully."), alert=True)

	@frappe.whitelist()
	def cancel_delivery(self, recipients: list[str]) -> None:
		"""Cancels delivery of a message to specific recipients."""

		frappe.only_for("System Manager")

		recipients = list(set(recipients))
		for recipient in recipients:
			cancel_message(self.name, recipient)

		frappe.msgprint(_("Delivery cancelled successfully."), alert=True)


@frappe.whitelist()
def get_queue_status(cluster_name: str) -> bool:
	"""Returns the status of the message queue for a given cluster."""

	frappe.only_for("System Manager")
	return bool(frappe.cache.get_value(get_status_cache_key(cluster_name)))


@frappe.whitelist()
def pause_queue(cluster_name: str) -> None:
	"""Pauses queue processing on the mail server."""

	frappe.only_for("System Manager")
	stop_queue_processing(cluster_name)
	frappe.msgprint(_("Queue paused successfully."), alert=True)


@frappe.whitelist()
def resume_queue(cluster_name: str) -> None:
	"""Resumes queue processing on the mail server."""

	frappe.only_for("System Manager")
	start_queue_processing(cluster_name)
	frappe.msgprint(_("Queue resumed successfully."), alert=True)


@frappe.whitelist()
def bulk_retry_delivery(names: str | list[str]) -> None:
	"""Retries delivery of messages to all recipients."""

	frappe.only_for("System Manager")

	if isinstance(names, str):
		names = json.loads(names)

	for name in names:
		retry_message(name)

	frappe.msgprint(_("Delivery retried successfully."), alert=True)


def fetch_messages(cluster_name: str, page: int = 1, limit: int = 10, text: str | None = None) -> list:
	"""Fetches a list of messages from the mail server."""

	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(
		method="GET",
		endpoint="/api/queue/messages",
		params={"page": page, "limit": limit, "values": 1, "text": text},
	)

	data = response.json()["data"]
	frappe.cache.set_value(get_status_cache_key(cluster_name), data["status"], expires_in_sec=600)
	frappe.cache.set_value(get_total_cache_key(cluster_name, text), data["total"], expires_in_sec=600)

	return [format_message(item, cluster_name) for item in data["items"]]


def fetch_message_details(name: str) -> dict:
	"""Fetches details of a specific message from the mail server."""

	cluster_name, queue_id = name.split("|")
	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(method="GET", endpoint=f"/api/queue/messages/{queue_id}")

	message = response.json()["data"]
	message["recipients"] = extract_recipients(message)
	message = format_message(message, cluster_name)
	message["message"] = fetch_blob(cluster_name, message["blob_hash"])

	return message


def fetch_blob(cluster_name: str, blob_id: str) -> str:
	"""Fetches a blob (email content) from the mail server."""

	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(method="GET", endpoint=f"/api/store/blobs/{blob_id}")
	return response.text


def retry_message(name: str) -> None:
	"""Retries delivery of a message to all recipients."""

	cluster_name, queue_id = name.split("|")
	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	backend_api.request(method="PATCH", endpoint=f"/api/queue/messages/{queue_id}")


def cancel_message(name: str, recipient: str | None = None) -> None:
	"""Cancels delivery of a message to specific recipients."""

	cluster_name, queue_id = name.split("|")
	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	backend_api.request(
		method="DELETE", endpoint=f"/api/queue/messages/{queue_id}", params={"filter": recipient}
	)


def stop_queue_processing(cluster_name: str) -> None:
	"""Stops queue processing on the mail server."""

	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	backend_api.request(
		method="PATCH",
		endpoint="/api/queue/status/stop",
	)


def start_queue_processing(cluster_name: str) -> None:
	"""Starts queue processing on the mail server."""

	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	backend_api.request(
		method="PATCH",
		endpoint="/api/queue/status/start",
	)


def get_status_cache_key(cluster_name: str) -> str:
	"""Returns a cache key for message status."""

	return f"{cluster_name}:message-queue:status"


def get_total_cache_key(cluster_name: str, text: str | None = None) -> str:
	"""Returns a cache key for total message count."""

	text = text or ""
	return f"{cluster_name}:message-queue:{text}:total"


def extract_recipients(message: dict) -> list:
	"""Extracts recipient details from a message dictionary."""

	recipients = []
	for recipient in message["recipients"]:
		status = "Scheduled"

		server_response = None
		if recipient["status"] != status.lower():
			rcpt_status = recipient["status"]
			if rcpt_status.get("temp_fail", False):
				status = "Temporary Failure"
			elif rcpt_status.get("perm_fail", False):
				status = "Permanent Failure"

			server_response = json.dumps(rcpt_status, indent=4)

		recipients.append(
			{
				"email": recipient["address"],
				"domain_name": recipient["address"].split("@")[-1],
				"original_rcpt": recipient.get("orcpt"),
				"status": status,
				"queue": recipient["queue"],
				"retry_num": recipient["retry_num"],
				"next_retry": recipient["next_retry"],
				"next_notify": recipient["next_notify"],
				"expires": recipient.get("expires"),
				"server_response": server_response,
			}
		)

	return recipients


def format_message(message: dict, cluster_name: str) -> dict:
	"""Formats a message dictionary to match expected output."""

	message = rename_keys(
		message,
		{
			"id": "queue_id",
			"size": "message_size",
			"created": "created_at",
		},
	)

	message.update(
		{
			"cluster": cluster_name,
			"creation": message["created_at"],
			"modified": message["created_at"],
			"name": f"{cluster_name}|{message['queue_id']}",
			"domains": json.dumps(message.get("domains", []), indent=4),
		}
	)

	return message
