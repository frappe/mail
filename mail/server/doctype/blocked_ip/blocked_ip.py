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


class BlockedIP(Document):
	@property
	def host(self) -> str | None:
		"""Returns the host name of the IP address."""

		if self.ip_address:
			return get_host_by_ip(self.ip_address)

	def autoname(self) -> None:
		self.name = f"{self.cluster}|{self.ip_address}"

	def db_insert(self, *args, **kwargs) -> None:
		BlockedIP._create(self.cluster, self.ip_address)

	def load_from_db(self) -> "BlockedIP":
		cluster, ip_address = self.name.split("|")
		blocked_ip = BlockedIP._read(cluster, ip_address)
		return super(Document, self).__init__(blocked_ip)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		cluster, ip_address = self.name.split("|")
		BlockedIP._delete(cluster, ip_address)

		if not frappe.flags.in_bulk_delete:
			frappe.msgprint(_("Blocked IP removed successfully."), alert=True)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = filters or []
		cluster, ip_address = extract_filter_values(filters, [{"cluster": "="}, {"ip_address": "like"}])

		if cluster:
			blocked_ips = BlockedIP._read_all(cluster, limit=page_length, text=ip_address)
			if not blocked_ips:
				frappe.msgprint(_("No blocked IPs found."), alert=True)

			return blocked_ips

		frappe.msgprint(_("Please select a cluster to view blocked IPs."), alert=True)
		return []

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = filters or []
		cluster, ip_address = extract_filter_values(filters, [{"cluster": "="}, {"ip_address": "like"}])

		return frappe.cache.get_value(get_total_cache_key(cluster, ip_address)) if cluster else 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	@staticmethod
	def _create(cluster: str, ip_address: str | list[str]) -> None:
		ip_addresses = [ip_address] if isinstance(ip_address, str) else ip_address
		request_data = []
		for ip in ip_addresses:
			request_data.append(
				{
					"type": "insert",
					"prefix": None,
					"values": [[f"server.blocked-ip.{ip}", ""]],
					"assert_empty": True,
				}
			)

		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		backend_api.request(
			method="POST",
			endpoint="/api/settings",
			data=json.dumps(request_data),
		)

	@staticmethod
	def _read(cluster: str, ip_address: str) -> None:
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		response = backend_api.request(
			method="GET",
			endpoint="api/settings/group",
			params={"prefix": "server.blocked-ip", "limit": 1, "filter": ip_address},
		)

		blocked_ip = response.json()["data"]["items"][0]
		return BlockedIP._format(blocked_ip, cluster)

	@staticmethod
	def _read_all(cluster: str, page: int = 1, limit: int = 10, text: str | None = None) -> list:
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		response = backend_api.request(
			method="GET",
			endpoint="api/settings/group",
			params={"page": page, "prefix": "server.blocked-ip", "limit": limit, "filter": text},
		)

		data = response.json()["data"]
		frappe.cache.set_value(get_total_cache_key(cluster, text), data["total"], expires_in_sec=600)

		return [BlockedIP._format(item, cluster) for item in data["items"]]

	@staticmethod
	def _update() -> None:
		raise NotImplementedError

	@staticmethod
	def _delete(cluster: str, ip_address: str | list[str]) -> None:
		ip_addresses = [ip_address] if isinstance(ip_address, str) else ip_address
		request_data = []
		for ip in ip_addresses:
			request_data.append({"type": "delete", "keys": [f"server.blocked-ip.{ip}"]})

		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		backend_api.request(
			method="POST",
			endpoint="/api/settings",
			data=json.dumps(request_data),
		)

	@staticmethod
	def _format(blocked_ip: dict, cluster: str) -> dict:
		return {
			"cluster": cluster,
			"ip_address": blocked_ip["_id"],
			"name": f"{cluster}|{blocked_ip['_id']}",
			"creation": today(),
			"modified": today(),
		}


def get_total_cache_key(cluster_name: str, text: str | None = None) -> str:
	"""Returns a cache key for total blocked IP count."""

	text = text or ""
	return f"{cluster_name}:blocked-ip:{text}:total"
