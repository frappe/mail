# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _

from mail.mail.doctype.dmarc_report.dmarc_report import DMARCReport


def execute(filters: dict | None = None) -> tuple:
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Name"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "DMARC Report",
			"width": 200,
		},
		{"label": _("Report Begin"), "fieldname": "report_begin", "fieldtype": "Datetime", "width": 180},
		{"label": _("report_end"), "fieldname": "report_end", "fieldtype": "Datetime", "width": 180},
		{
			"label": _("Domain Name"),
			"fieldname": "domain_name",
			"fieldtype": "Link",
			"options": "Mail Domain",
			"width": 150,
		},
		{"label": _("Organization"), "fieldname": "organization_name", "fieldtype": "Data", "width": 150},
		{"label": _("Report ID"), "fieldname": "report_id", "fieldtype": "Data", "width": 150},
		{"label": _("Source IP"), "fieldname": "source_ip", "fieldtype": "Data", "width": 150},
		{"label": _("Count"), "fieldname": "count", "fieldtype": "Int", "width": 70},
		{"label": _("Disposition"), "fieldname": "disposition", "fieldtype": "Data", "width": 150},
		{"label": _("Header From"), "fieldname": "header_from", "fieldtype": "Data", "width": 150},
		{"label": _("Envelope From"), "fieldname": "envelope_from", "fieldtype": "Data", "width": 150},
		{"label": _("Envelope To"), "fieldname": "envelope_to", "fieldtype": "Data", "width": 150},
		{"label": _("DKIM Result"), "fieldname": "dkim_result", "fieldtype": "Data", "width": 150},
		{"label": _("SPF Result"), "fieldname": "spf_result", "fieldtype": "Data", "width": 150},
		{"label": _("Auth Type"), "fieldname": "auth_type", "fieldtype": "Data", "width": 150},
		{"label": _("Selector"), "fieldname": "selector", "fieldtype": "Data", "width": 150},
		{"label": _("Scope"), "fieldname": "scope", "fieldtype": "Data", "width": 150},
		{"label": _("Domain"), "fieldname": "domain", "fieldtype": "Data", "width": 150},
		{"label": _("Result"), "fieldname": "result", "fieldtype": "Data", "width": 150},
	]


def get_data(filters: dict | None = None) -> list[list]:
	filters = filters or {}
	local_ips = get_local_ip_addresses()
	dmarc_reports = DMARCReport.get_list(filters)

	data = []
	for dmarc_report in dmarc_reports:
		records = dmarc_report.pop("records", [])

		if not records:
			continue

		dmarc_report["indent"] = 0
		data.append(dmarc_report)

		for record in records:
			record["indent"] = 1
			record["is_local_ip"] = record["source_ip"] in local_ips
			record["dkim_result"] = record["dkim_result"].upper()
			record["spf_result"] = record["spf_result"].upper()
			data.append(record)

			for field in ["dkim_results", "spf_results"]:
				for result in json.loads(record[field]):
					result["indent"] = 2
					result["auth_type"] = field.replace("_results", "").upper()
					result["result"] = result["result"].upper()
					data.append(result)

	return data


def get_local_ip_addresses() -> list[str]:
	"""Returns list of local IPs (Mail Servers IPs)."""

	ip_addresses = []
	for addresses in frappe.db.get_all("Mail Server", {}, ["ipv4_addresses", "ipv6_addresses"]):
		for field in ["ipv4_addresses", "ipv6_addresses"]:
			ip_addresses.extend(addresses[field].split("\n") if addresses[field] else [])

	return ip_addresses
