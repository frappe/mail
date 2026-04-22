# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from mail.backend import get_mail_backend_api
from mail.utils import extract_filter_values
from mail.utils.dns import get_host_by_ip


class AllowedIP(Document):
	@property
	def host(self) -> str | None:
		"""Returns the host name of the IP address."""

		if self.ip_address:
			return get_host_by_ip(self.ip_address)

	def autoname(self) -> None:
		self.name = self.ip_address

	def db_insert(self, *args, **kwargs) -> None:
		self._create()

	def load_from_db(self) -> "AllowedIP":
		allowed_ip = self._get()
		return super(Document, self).__init__(allowed_ip)

	def db_update(self) -> None:
		self._update()

	def delete(self) -> None:
		self._delete()
		if not frappe.flags.in_bulk_delete:
			frappe.msgprint(_("Allowed IP removed successfully."), alert=True)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = filters or []
		ip_address = extract_filter_values(filters, [{"ip_address": "like"}])

		if ip_address:
			allowed_ips = AllowedIP._get_all(limit=page_length, text=ip_address)
			if not allowed_ips:
				frappe.msgprint(_("No allowed IPs found."), alert=True)

			return allowed_ips

		return []

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = filters or []
		ip_address = extract_filter_values(filters, [{"ip_address": "like"}])

		return frappe.cache.get_value(get_total_cache_key(ip_address)) if ip_address else 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	def _create(self) -> None:
		"""Creates the allowed IP in the backend."""

		ip_addresses = [self.ip_address]
		request_data = []
		for ip in ip_addresses:
			request_data.append(
				{
					"type": "insert",
					"prefix": None,
					"values": [[f"server.allowed-ip.{ip}", ""]],
					"assert_empty": True,
				}
			)

		backend_api = get_mail_backend_api()
		backend_api.request(
			method="POST",
			endpoint="/api/settings",
			data=json.dumps(request_data),
		)

	def _get(self) -> None:
		"""Returns the allowed IP from the backend."""

		ip_address = self.name
		backend_api = get_mail_backend_api()
		response = backend_api.request(
			method="GET",
			endpoint="api/settings/group",
			params={"prefix": "server.allowed-ip", "limit": 1, "filter": ip_address},
		)

		allowed_ip = response.json()["data"]["items"][0]
		return AllowedIP._format(allowed_ip)

	@staticmethod
	def _get_all(page: int = 1, limit: int = 10, text: str | None = None) -> list:
		"""Returns all allowed IPs."""
		backend_api = get_mail_backend_api()
		response = backend_api.request(
			method="GET",
			endpoint="api/settings/group",
			params={"page": page, "prefix": "server.allowed-ip", "limit": limit, "filter": text},
		)

		data = response.json()["data"]
		frappe.cache.set_value(get_total_cache_key(text), data["total"], expires_in_sec=600)

		return [AllowedIP._format(item) for item in data["items"]]

	def _update(self) -> None:
		raise NotImplementedError

	def _delete(self) -> None:
		"""Deletes the allowed IP from the backend."""

		ip_addresses = [self.ip_address]
		request_data = []
		for ip in ip_addresses:
			request_data.append({"type": "delete", "keys": [f"server.allowed-ip.{ip}"]})

		backend_api = get_mail_backend_api()
		backend_api.request(
			method="POST",
			endpoint="/api/settings",
			data=json.dumps(request_data),
		)

	@staticmethod
	def _format(allowed_ip: dict) -> dict:
		"""Formats the allowed IP data from the backend."""

		return {
			"ip_address": allowed_ip["_id"],
			"name": allowed_ip["_id"],
			"creation": today(),
			"modified": today(),
		}


def get_total_cache_key(text: str | None = None) -> str:
	"""Returns a cache key for total allowed IP count."""

	text = text or ""
	return f"allowed-ip:{text}:total"
