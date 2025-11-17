# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now

from mail.backend import get_mail_backend_api
from mail.utils import extract_filter_values, rename_keys
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
		add_blocked_ip(self.cluster, self.ip_address)

	def load_from_db(self) -> "BlockedIP":
		blocked_ip = fetch_blocked_ip_details(self.name)
		return super(Document, self).__init__(blocked_ip)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		remove_blocked_ip(self.name)

		if not frappe.flags.in_bulk_delete:
			frappe.msgprint(_("Blocked IP removed successfully."), alert=True)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = filters or []
		cluster, ip_address = extract_filter_values(filters, [{"cluster": "="}, {"ip_address": "like"}])

		if cluster:
			blocked_ips = fetch_blocked_ips(cluster, limit=page_length, text=ip_address)
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


def get_total_cache_key(cluster_name: str, text: str | None = None) -> str:
	"""Returns a cache key for total blocked IP count."""

	text = text or ""
	return f"{cluster_name}:blocked-ip:{text}:total"


def add_blocked_ip(cluster_name: str, ip_address: str | list) -> None:
	"""Adds a blocked ip to the mail server."""

	if isinstance(ip_address, str):
		ip_address = [ip_address]

	request_data = []
	for ip in ip_address:
		request_data.append(
			{
				"type": "insert",
				"prefix": None,
				"values": [[f"server.blocked-ip.{ip}", ""]],
				"assert_empty": True,
			}
		)

	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(
		method="POST",
		endpoint="/api/settings",
		data=json.dumps(request_data),
	)

	if response.status_code != 200:
		frappe.throw(title=_("Request failed for {0}").format(backend_api.base_url), msg=response.text)


def fetch_blocked_ips(cluster_name: str, page: int = 1, limit: int = 10, text: str | None = None) -> list:
	"""Fetches a list of blocked ips from the mail server."""

	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(
		method="GET",
		endpoint="api/settings/group",
		params={"page": page, "prefix": "server.blocked-ip", "limit": limit, "filter": text},
	)

	if response.status_code == 200:
		data = response.json()["data"]
		frappe.cache.set_value(get_total_cache_key(cluster_name, text), data["total"], expires_in_sec=600)

		return [format_blocked_ip(item, cluster_name) for item in data["items"]]

	frappe.throw(title=_("Request failed for {0}").format(backend_api.base_url), msg=response.text)


def fetch_blocked_ip_details(name: str) -> dict:
	"""Fetches details of a specific blocked ip from the mail server."""

	cluster_name, ip_address = name.split("|")
	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(
		method="GET",
		endpoint="api/settings/group",
		params={"prefix": "server.blocked-ip", "limit": 1, "filter": ip_address},
	)

	if response.status_code == 200:
		blocked_ip = response.json()["data"]["items"][0]

		return format_blocked_ip(blocked_ip, cluster_name)

	frappe.throw(title=_("Request failed for {0}").format(backend_api.base_url), msg=response.text)


def remove_blocked_ip(name: str | list) -> None:
	"""Removes a blocked ip from the mail server."""

	if isinstance(name, str):
		name = [name]

	request_data = []
	for n in name:
		cluster_name, ip_address = n.split("|")
		request_data.append({"type": "delete", "keys": [f"server.blocked-ip.{ip_address}"]})

	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(
		method="POST",
		endpoint="/api/settings",
		data=json.dumps(request_data),
	)

	if response.status_code != 200:
		frappe.throw(title=_("Request failed for {0}").format(backend_api.base_url), msg=response.text)


def format_blocked_ip(blocked_ip: dict, cluster_name: str) -> dict:
	"""Formats a blocked ip dictionary to match expected output."""

	creation = now()
	blocked_ip = rename_keys(blocked_ip, {"id": "ip_address"})
	blocked_ip.update(
		{
			"creation": creation,
			"modified": creation,
			"cluster": cluster_name,
			"name": f"{cluster_name}|{blocked_ip['ip_address']}",
		}
	)

	return blocked_ip
