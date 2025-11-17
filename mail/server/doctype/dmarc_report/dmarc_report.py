# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from datetime import datetime, timezone

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, convert_utc_to_system_timezone, get_datetime_str, now

from mail.backend import get_mail_backend_api
from mail.utils import extract_filter_values


class DMARCReport(Document):
	def autoname(self) -> None:
		self.name = f"{self.cluster}|{self.id}"

	def db_insert(self, *args, **kwargs) -> None:
		raise NotImplementedError

	def load_from_db(self) -> "DMARCReport":
		report = fetch_dmarc_report_details(self.name)
		return super(Document, self).__init__(report)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		remove_dmarc_report(self.name)

		if not frappe.flags.in_bulk_delete:
			frappe.msgprint(_("DMARC report removed successfully."), alert=True)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = filters or []
		cluster, text = None, None

		if isinstance(filters, dict):
			cluster = filters.get("cluster")
			text = filters.get("text")
		elif isinstance(filters, list):
			cluster, text = extract_filter_values(filters, [{"cluster": "="}, {"text": "like"}])

		if cluster:
			reports = fetch_dmarc_reports(cluster, limit=page_length, text=text)
			if not reports:
				frappe.msgprint(_("No DMARC reports found."), alert=True)

			return reports

		frappe.msgprint(_("Please select a cluster to view DMARC reports."), alert=True)
		return []

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = filters or []
		cluster, text = extract_filter_values(filters, [{"cluster": "="}, {"text": "like"}])

		return frappe.cache.get_value(get_total_cache_key(cluster, text)) if cluster else 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}


def get_total_cache_key(cluster_name: str, text: str | None = None) -> str:
	"""Returns a cache key for total reports count."""

	text = text or ""
	return f"{cluster_name}:dmarc_reports:{text}:total"


def fetch_dmarc_reports(cluster_name: str, page: int = 1, limit: int = 10, text: str | None = None) -> list:
	"""Fetches DMARC reports from the mail server."""

	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(
		method="GET",
		endpoint="api/reports/dmarc",
		params={"page": page, "limit": limit, "filter": text},
	)

	if response.status_code == 200:
		data = response.json()["data"]
		frappe.cache.set_value(get_total_cache_key(cluster_name, text), data["total"], expires_in_sec=600)

		return [fetch_dmarc_report_details(f"{cluster_name}|{id}") for id in data["items"]]

	frappe.throw(title=_("Request failed for {0}").format(backend_api.base_url), msg=response.text)


def fetch_dmarc_report_details(name: str) -> dict:
	"""Fetches details of a specific DMARC report from the mail server."""

	if report := frappe.cache.hget("dmarc_reports", name):
		return report

	cluster_name, id = name.split("|")
	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(method="GET", endpoint=f"/api/reports/dmarc/{id}")

	if response.status_code == 200:
		report = response.json()["data"]
		report["id"] = id
		report = format_report(report, cluster_name)
		frappe.cache.hset("dmarc_reports", name, report)

		return report

	frappe.throw(title=_("Request failed for {0}").format(backend_api.base_url), msg=response.text)


def remove_dmarc_report(name: str) -> None:
	"""Removes a DMARC report from the mail server."""

	cluster_name, id = name.split("|")
	backend_api = get_mail_backend_api("Mail Cluster", cluster_name)
	response = backend_api.request(method="DELETE", endpoint=f"/api/reports/dmarc/{id}")
	if response.status_code != 200:
		frappe.throw(title=_("Request failed for {0}").format(backend_api.base_url), msg=response.text)


def format_report(report: dict, cluster_name: str) -> dict:
	"""Formats the DMARC report data for display."""

	report_begin = get_datetime_str(
		convert_utc_to_system_timezone(
			datetime.fromtimestamp(
				int(report["report"]["report_metadata"]["date_range"]["begin"]), tz=timezone.utc
			)
		)
	)
	report_end = get_datetime_str(
		convert_utc_to_system_timezone(
			datetime.fromtimestamp(
				int(report["report"]["report_metadata"]["date_range"]["end"]), tz=timezone.utc
			)
		)
	)

	formatted_report = {
		"id": report["id"],
		"cluster": cluster_name,
		"name": f"{cluster_name}|{report['id']}",
		"report_id": report["report"]["report_metadata"]["report_id"],
		"organization_name": report["report"]["report_metadata"]["org_name"],
		"email": report["report"]["report_metadata"]["email"],
		"extra_contact_info": report["report"]["report_metadata"]["extra_contact_info"],
		"received_from": report["from"],
		"report_begin": report_begin,
		"report_end": report_end,
		"subject": report["subject"],
		"domain_name": report["report"]["policy_published"]["domain"],
		"dkim_alignment": report["report"]["policy_published"]["adkim"],
		"spf_alignment": report["report"]["policy_published"]["aspf"],
		"domain_policy": report["report"]["policy_published"]["p"],
		"subdomain_policy": report["report"]["policy_published"]["sp"],
		"records": [],
		"creation": now(),
		"modified": now(),
	}

	for record in report["report"]["record"]:
		formatted_report["records"].append(
			{
				"source_ip": record["row"]["source_ip"],
				"count": cint(record["row"]["count"]),
				"disposition": record["row"]["policy_evaluated"]["disposition"],
				"dkim_result": record["row"]["policy_evaluated"]["dkim"],
				"spf_result": record["row"]["policy_evaluated"]["spf"],
				"reason": json.dumps(record["row"]["policy_evaluated"]["reason"], indent=4),
				"envelope_to": record["identifiers"]["envelope_to"],
				"envelope_from": record["identifiers"]["envelope_from"],
				"header_from": record["identifiers"]["header_from"],
				"dkim_results": json.dumps(record["auth_results"]["dkim"], indent=4),
				"spf_results": json.dumps(record["auth_results"]["spf"], indent=4),
			}
		)

	return formatted_report
