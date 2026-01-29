# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from datetime import UTC, datetime, timezone

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
		self._create()

	def load_from_db(self) -> "DMARCReport":
		report = self._get()
		return super(Document, self).__init__(report)

	def db_update(self) -> None:
		self._update()

	def delete(self) -> None:
		self._delete(self)
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
			reports = DMARCReport._get_all(cluster, limit=page_length, text=text)
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

	def _create(self) -> None:
		raise NotImplementedError

	def _get(self) -> None:
		"""Returns DMARC report details from cache or backend."""

		cluster, id = self.name.split("|")
		if report := frappe.cache.hget("dmarc_reports", f"{cluster}|{id}"):
			return report

		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		response = backend_api.request(method="GET", endpoint=f"/api/reports/dmarc/{id}")

		report = response.json()["data"]
		report["id"] = id
		report = DMARCReport._format(report, cluster)
		frappe.cache.hset("dmarc_reports", f"{cluster}|{id}", report)

		return report

	@staticmethod
	def _get_all(cluster: str, page: int = 1, limit: int = 10, text: str | None = None) -> list:
		"""Returns list of DMARC reports from backend."""

		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		response = backend_api.request(
			method="GET",
			endpoint="api/reports/dmarc",
			params={"page": page, "limit": limit, "filter": text},
		)

		data = response.json()["data"]
		frappe.cache.set_value(get_total_cache_key(cluster, text), data["total"], expires_in_sec=600)

		return [DMARCReport._format(f"{cluster}|{id}") for id in data["items"]]

	def _update(self) -> None:
		raise NotImplementedError

	def _delete(self) -> None:
		"""Deletes DMARC report from backend and cache."""

		cluster, id = self.name.split("|")
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		backend_api.request(method="DELETE", endpoint=f"/api/reports/dmarc/{id}")

	@staticmethod
	def _format(report: dict, cluster: str) -> dict:
		"""Formats DMARC report data."""

		report_begin = get_datetime_str(
			convert_utc_to_system_timezone(
				datetime.fromtimestamp(
					int(report["report"]["report_metadata"]["date_range"]["begin"]), tz=UTC
				)
			)
		)
		report_end = get_datetime_str(
			convert_utc_to_system_timezone(
				datetime.fromtimestamp(int(report["report"]["report_metadata"]["date_range"]["end"]), tz=UTC)
			)
		)

		formatted_report = {
			"id": report["id"],
			"cluster": cluster,
			"name": f"{cluster}|{report['id']}",
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


def get_total_cache_key(cluster: str, text: str | None = None) -> str:
	"""Returns a cache key for total reports count."""

	text = text or ""
	return f"{cluster}:dmarc_reports:{text}:total"
