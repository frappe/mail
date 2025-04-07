# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now

from mail.mail_server import get_mail_server_api
from mail.utils import extract_filter_values, rename_keys


class AllowedIP(Document):
	def autoname(self) -> None:
		self.name = f"{self.cluster}-{self.ip_address}"

	def db_insert(self, *args, **kwargs) -> None:
		add_allowed_ip(self.cluster, self.ip_address)

	def load_from_db(self) -> "AllowedIP":
		allowed_ip = fetch_allowed_ip_details(self.name)
		return super(Document, self).__init__(allowed_ip)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		remove_allowed_ip(self.name)

		if not frappe.flags.in_bulk_delete:
			frappe.msgprint(_("Allowed IP removed successfully."), alert=True)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = filters or []
		cluster, ip_address = extract_filter_values(filters, [{"cluster": "="}, {"ip_address": "like"}])

		if cluster:
			allowed_ips = fetch_allowed_ips(cluster, limit=page_length, text=ip_address)
			if not allowed_ips:
				frappe.msgprint(_("No allowed IPs found."), alert=True)

			return allowed_ips

		frappe.msgprint(_("Please select a cluster to view allowed IPs."), alert=True)
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
	"""Returns a cache key for total allowed IP count."""

	text = text or ""
	return f"{cluster_name}:allowed-ip:{text}:total"


def add_allowed_ip(cluster_name: str, ip_address: str | list) -> None:
	"""Adds a allowed ip to the mail server."""

	if isinstance(ip_address, str):
		ip_address = [ip_address]

	request_data = []
	for ip in ip_address:
		request_data.append(
			{
				"type": "insert",
				"prefix": None,
				"values": [[f"server.allowed-ip.{ip}", ""]],
				"assert_empty": True,
			}
		)

	server_api = get_mail_server_api(cluster_name)
	response = server_api.request(
		method="POST",
		endpoint="/api/settings",
		data=json.dumps(request_data),
	)

	if response.status_code != 200:
		frappe.throw(title=_("Request failed for {0}").format(server_api.base_url), msg=response.text)


def fetch_allowed_ips(cluster_name: str, page: int = 1, limit: int = 10, text: str | None = None) -> list:
	"""Fetches a list of allowed ips from the mail server."""

	server_api = get_mail_server_api(cluster_name)
	response = server_api.request(
		method="GET",
		endpoint="api/settings/group",
		params={"page": page, "prefix": "server.allowed-ip", "limit": limit, "filter": text},
	)

	if response.status_code == 200:
		data = response.json()["data"]
		frappe.cache.set_value(get_total_cache_key(cluster_name, text), data["total"], expires_in_sec=600)

		return [format_allowed_ip(item, cluster_name) for item in data["items"]]

	frappe.throw(title=_("Request failed for {0}").format(server_api.base_url), msg=response.text)


def fetch_allowed_ip_details(name: str) -> dict:
	"""Fetches details of a specific allowed ip from the mail server."""

	cluster_name, ip_address = name.split("-")
	server_api = get_mail_server_api(cluster_name)
	response = server_api.request(
		method="GET",
		endpoint="api/settings/group",
		params={"prefix": "server.allowed-ip", "limit": 1, "filter": ip_address},
	)

	if response.status_code == 200:
		allowed_ip = response.json()["data"]["items"][0]

		return format_allowed_ip(allowed_ip, cluster_name)

	frappe.throw(title=_("Request failed for {0}").format(server_api.base_url), msg=response.text)


def remove_allowed_ip(name: str | list) -> None:
	"""Removes a allowed ip from the mail server."""

	if isinstance(name, str):
		name = [name]

	request_data = []
	for n in name:
		cluster_name, ip_address = n.split("-")
		request_data.append({"type": "delete", "keys": [f"server.allowed-ip.{ip_address}"]})

	server_api = get_mail_server_api(cluster_name)
	response = server_api.request(
		method="POST",
		endpoint="/api/settings",
		data=json.dumps(request_data),
	)

	if response.status_code != 200:
		frappe.throw(title=_("Request failed for {0}").format(server_api.base_url), msg=response.text)


def format_allowed_ip(allowed_ip: dict, cluster_name: str) -> dict:
	"""Formats a allowed ip dictionary to match expected output."""

	creation = now()
	allowed_ip = rename_keys(allowed_ip, {"_id": "ip_address"})
	allowed_ip.update(
		{
			"creation": creation,
			"modified": creation,
			"cluster": cluster_name,
			"name": f"{cluster_name}-{allowed_ip['ip_address']}",
		}
	)

	return allowed_ip
