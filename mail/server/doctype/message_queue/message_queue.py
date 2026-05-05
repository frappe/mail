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
		raise self._create()

	def load_from_db(self) -> "MessageQueue":
		message = self._get()
		return super(Document, self).__init__(message)

	def db_update(self) -> None:
		MessageQueue._update(self.name)

	def delete(self) -> None:
		self._delete()
		if not frappe.flags.in_bulk_delete:
			frappe.msgprint(_("Message deleted successfully."), alert=True)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = filters or []
		text = extract_filter_values(filters, [{"text": "like"}])[0]

		messages = MessageQueue._get_all(limit=page_length, text=text)
		if not messages:
			frappe.msgprint(_("No messages found."), alert=True)

		return messages

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = filters or []
		text = extract_filter_values(filters, [{"text": "like"}])[0]

		return frappe.cache.get_value(get_total_cache_key(text)) if text else 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	@frappe.whitelist()
	def retry_delivery(self) -> None:
		"""Retries delivery of a message to all recipients."""

		frappe.only_for("System Manager")
		MessageQueue._update(self.name)
		frappe.msgprint(_("Delivery retried successfully."), alert=True)

	@frappe.whitelist()
	def cancel_delivery(self, recipients: list[str]) -> None:
		"""Cancels delivery of a message to specific recipients."""

		frappe.only_for("System Manager")

		recipients = list(set(recipients))
		for recipient in recipients:
			self._delete(recipient)

		frappe.msgprint(_("Delivery cancelled successfully."), alert=True)

	def _create(self) -> None:
		raise NotImplementedError

	def _get(self) -> dict:
		"""Returns the message details from the server."""

		backend_api = get_mail_backend_api()
		response = backend_api.request(method="GET", endpoint=f"/api/queue/messages/{self.name}")

		message = response.json()["data"]
		message = MessageQueue._format(message, extract_recipients=True)
		message["message"] = MessageQueue._get_blob(message["blob_hash"])

		return message

	@staticmethod
	def _get_blob(blob_id: str) -> str:
		"""Returns the raw message blob from the server."""

		backend_api = get_mail_backend_api()
		response = backend_api.request(method="GET", endpoint=f"/api/store/blobs/{blob_id}")
		return response.text.strip()

	@staticmethod
	def _get_all(page: int = 1, limit: int = 10, text: str | None = None) -> list:
		"""Returns all messages from the server."""

		backend_api = get_mail_backend_api()
		response = backend_api.request(
			method="GET",
			endpoint="/api/queue/messages",
			params={"page": page, "limit": limit, "values": 1, "text": text},
		)

		data = response.json()["data"]
		frappe.cache.set_value(get_status_cache_key(), data["status"], expires_in_sec=600)
		frappe.cache.set_value(get_total_cache_key(text), data["total"], expires_in_sec=600)

		return [MessageQueue._format(item) for item in data["items"]]

	@staticmethod
	def _update(name: str) -> None:
		"""Retries delivery of a message to all recipients."""

		backend_api = get_mail_backend_api()
		backend_api.request(method="PATCH", endpoint=f"/api/queue/messages/{name}")

	def _delete(self, recipient: str | None = None) -> None:
		"""Deletes a message or cancels delivery to a specific recipient."""

		backend_api = get_mail_backend_api()
		backend_api.request(
			method="DELETE", endpoint=f"/api/queue/messages/{self.name}", params={"filter": recipient}
		)

	@staticmethod
	def _pause() -> None:
		"""Pauses queue processing on the server."""

		backend_api = get_mail_backend_api()
		backend_api.request(
			method="PATCH",
			endpoint="/api/queue/status/stop",
		)

	@staticmethod
	def _resume() -> None:
		"""Resumes queue processing on the server."""

		backend_api = get_mail_backend_api()
		backend_api.request(
			method="PATCH",
			endpoint="/api/queue/status/start",
		)

	@staticmethod
	def _format(message: dict, extract_recipients: bool = False) -> dict:
		"""Formats the message details."""

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
				"size": "message_size",
				"created": "created_at",
			},
		)

		message.update(
			{
				"name": str(message.pop("id")),
				"creation": message["created_at"],
				"modified": message["created_at"],
				"domains": json.dumps(message.get("domains", []), indent=4),
			}
		)

		return message


@frappe.whitelist()
def get_queue_status() -> bool:
	"""Returns the status of the message queue."""

	frappe.only_for("System Manager")
	return bool(frappe.cache.get_value(get_status_cache_key()))


@frappe.whitelist()
def pause_queue() -> None:
	"""Pauses queue processing on the mail server."""

	frappe.only_for("System Manager")
	MessageQueue._pause()
	frappe.msgprint(_("Queue paused successfully."), alert=True)


@frappe.whitelist()
def resume_queue() -> None:
	"""Resumes queue processing on the mail server."""

	frappe.only_for("System Manager")
	MessageQueue._resume()
	frappe.msgprint(_("Queue resumed successfully."), alert=True)


@frappe.whitelist()
def bulk_retry_delivery(names: str | list[str]) -> None:
	"""Retries delivery of messages to all recipients."""

	frappe.only_for("System Manager")

	if isinstance(names, str):
		names = json.loads(names)

	for name in names:
		MessageQueue._update(name)

	frappe.msgprint(_("Delivery retried successfully."), alert=True)


def get_status_cache_key() -> str:
	"""Returns a cache key for message status."""

	return "message-queue:status"


def get_total_cache_key(text: str | None = None) -> str:
	"""Returns a cache key for total message count."""

	text = text or ""
	return f"message-queue:{text}:total"
