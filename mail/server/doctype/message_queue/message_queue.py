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
		cluster, id = self.name.split("|")
		message = MessageQueue._get(cluster, id)
		return super(Document, self).__init__(message)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		cluster, id = self.name.split("|")
		MessageQueue._delete(cluster, id)

		if not frappe.flags.in_bulk_delete:
			frappe.msgprint(_("Message deleted successfully."), alert=True)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = filters or []
		cluster, text = extract_filter_values(filters, [{"cluster": "="}, {"text": "like"}])

		if cluster:
			messages = MessageQueue._get_all(cluster, limit=page_length, text=text)
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
		cluster, id = self.name.split("|")
		MessageQueue._update(cluster, id)
		frappe.msgprint(_("Delivery retried successfully."), alert=True)

	@frappe.whitelist()
	def cancel_delivery(self, recipients: list[str]) -> None:
		"""Cancels delivery of a message to specific recipients."""

		frappe.only_for("System Manager")

		cluster, id = self.name.split("|")
		recipients = list(set(recipients))
		for recipient in recipients:
			MessageQueue._delete(cluster, id, recipient)

		frappe.msgprint(_("Delivery cancelled successfully."), alert=True)

	@staticmethod
	def _create() -> None:
		raise NotImplementedError

	@staticmethod
	def _get(cluster: str, id: str) -> None:
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		response = backend_api.request(method="GET", endpoint=f"/api/queue/messages/{id}")

		message = response.json()["data"]
		message = MessageQueue._format(message, cluster, extract_recipients=True)
		message["message"] = MessageQueue._get_blob(cluster, message["blob_hash"])

		return message

	@staticmethod
	def _get_blob(cluster: str, blob_id: str) -> str:
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		response = backend_api.request(method="GET", endpoint=f"/api/store/blobs/{blob_id}")
		return response.text.strip()

	@staticmethod
	def _get_all(cluster: str, page: int = 1, limit: int = 10, text: str | None = None) -> list:
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		response = backend_api.request(
			method="GET",
			endpoint="/api/queue/messages",
			params={"page": page, "limit": limit, "values": 1, "text": text},
		)

		data = response.json()["data"]
		frappe.cache.set_value(get_status_cache_key(cluster), data["status"], expires_in_sec=600)
		frappe.cache.set_value(get_total_cache_key(cluster, text), data["total"], expires_in_sec=600)

		return [MessageQueue._format(item, cluster) for item in data["items"]]

	@staticmethod
	def _update(cluster: str, id: str) -> None:
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		backend_api.request(method="PATCH", endpoint=f"/api/queue/messages/{id}")

	@staticmethod
	def _delete(cluster: str, id: str, recipient: str | None = None) -> None:
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		backend_api.request(
			method="DELETE", endpoint=f"/api/queue/messages/{id}", params={"filter": recipient}
		)

	@staticmethod
	def _pause(cluster: str) -> None:
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		backend_api.request(
			method="PATCH",
			endpoint="/api/queue/status/stop",
		)

	@staticmethod
	def _resume(cluster: str) -> None:
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		backend_api.request(
			method="PATCH",
			endpoint="/api/queue/status/start",
		)

	@staticmethod
	def _format(message: dict, cluster: str, extract_recipients: bool = False) -> dict:
		if extract_recipients:
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

			message["recipients"] = recipients

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
				"cluster": cluster,
				"creation": message["created_at"],
				"modified": message["created_at"],
				"name": f"{cluster}|{message['queue_id']}",
				"domains": json.dumps(message.get("domains", []), indent=4),
			}
		)

		return message


@frappe.whitelist()
def get_queue_status(cluster: str) -> bool:
	"""Returns the status of the message queue for a given cluster."""

	frappe.only_for("System Manager")
	return bool(frappe.cache.get_value(get_status_cache_key(cluster)))


@frappe.whitelist()
def pause_queue(cluster: str) -> None:
	"""Pauses queue processing on the mail server."""

	frappe.only_for("System Manager")
	MessageQueue._pause(cluster)
	frappe.msgprint(_("Queue paused successfully."), alert=True)


@frappe.whitelist()
def resume_queue(cluster: str) -> None:
	"""Resumes queue processing on the mail server."""

	frappe.only_for("System Manager")
	MessageQueue._resume(cluster)
	frappe.msgprint(_("Queue resumed successfully."), alert=True)


@frappe.whitelist()
def bulk_retry_delivery(names: str | list[str]) -> None:
	"""Retries delivery of messages to all recipients."""

	frappe.only_for("System Manager")

	if isinstance(names, str):
		names = json.loads(names)

	for name in names:
		cluster, id = name.split("|")
		MessageQueue._update(cluster, id)

	frappe.msgprint(_("Delivery retried successfully."), alert=True)


def get_status_cache_key(cluster: str) -> str:
	"""Returns a cache key for message status."""

	return f"{cluster}:message-queue:status"


def get_total_cache_key(cluster: str, text: str | None = None) -> str:
	"""Returns a cache key for total message count."""

	text = text or ""
	return f"{cluster}:message-queue:{text}:total"
