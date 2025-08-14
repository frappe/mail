# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from functools import cached_property

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.backend import MailBackendDKIMManager, MailBackendDomainManager, get_mail_backend_api
from mail.jmap import raise_for_status
from mail.utils.cache import (
	get_cluster_for_tenant,
	get_root_domain_name,
	get_tenant_for_user,
)
from mail.utils.dns import verify_dns_record
from mail.utils.user import get_user_linked_domains, has_role, is_system_manager, is_tenant_admin


class MailDomain(Document):
	@cached_property
	def _dns_records(self) -> list[dict]:
		"""Fetch and normalize DNS Records for the Mail Domain."""

		if self.is_new() or not self.enabled:
			return []

		try:
			dns_records = self._fetch_dns_records()
			if not dns_records:
				return []

			mail_settings = frappe.get_cached_doc("Mail Settings")
			cluster = get_cluster_for_tenant(self.tenant)
			hostname = f"{frappe.db.get_value('Mail Cluster', cluster, 'hostname')}."
			cname_hostname = self._get_mail_cname_hostname(dns_records)
			cleaned_records = [
				self._normalize_record(
					record, mail_settings.spf_host, mail_settings.root_domain_name, hostname, cname_hostname
				)
				for record in dns_records
				if not self._should_skip_record(record)
			]

			return sorted(cleaned_records, key=lambda r: (r["mandatory"] == 0, r["type"], r["host"]))
		except Exception:
			frappe.log_error(
				title=_("Failed to fetch DNS Records for {0}").format(self.domain_name),
				message=frappe.get_traceback(with_context=True),
			)
			return []

	@property
	def dns_records(self) -> str:
		"""Returns the DNS Records in JSON format."""

		if dns_records := self._dns_records:
			return json.dumps(dns_records, indent=4)

		frappe.msgprint(_("Failed to fetch DNS Records."), indicator="red", alert=True)

	def autoname(self) -> None:
		self.domain_name = self.domain_name.strip().lower()
		self.name = self.domain_name

	def before_insert(self) -> None:
		self.validate_tenant()

	def validate(self) -> None:
		if self.is_new():
			self.validate_is_subdomain()
			self.validate_is_root_domain()

		self.validate_tenant()
		self.validate_is_verified()

	def after_insert(self) -> None:
		cluster = get_cluster_for_tenant(self.tenant)
		MailBackendDomainManager("Mail Cluster", cluster).create(self.domain_name)
		MailBackendDKIMManager("Mail Cluster", cluster).create(self.domain_name, algorithm="rsa")
		MailBackendDKIMManager("Mail Cluster", cluster).create(self.domain_name, algorithm="ed25519")

	def on_update(self) -> None:
		self.clear_cache()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Domain."))

		self.clear_cache()
		cluster = get_cluster_for_tenant(self.tenant)
		MailBackendDomainManager("Mail Cluster", cluster).delete(self.domain_name)
		MailBackendDKIMManager("Mail Cluster", cluster).delete(self.domain_name, algorithm="rsa")
		MailBackendDKIMManager("Mail Cluster", cluster).delete(self.domain_name, algorithm="ed25519")

	def validate_is_subdomain(self) -> None:
		"""Validates the Is Subdomain field."""

		if len(self.domain_name.split(".")) > 2:
			self.is_subdomain = 1

	def validate_is_root_domain(self) -> None:
		"""Validates the Is Root Domain field."""

		self.is_root_domain = 1 if self.domain_name == get_root_domain_name() else 0

	def validate_tenant(self) -> None:
		"""Validates the Tenant."""

		cluster, max_domains = frappe.db.get_value("Mail Tenant", self.tenant, ["cluster", "max_domains"])

		if not cluster:
			frappe.throw(_("Cluster is not set for Mail Tenant {0}.").format(frappe.bold(self.tenant)))

		total_domains = frappe.db.count("Mail Domain", filters={"tenant": self.tenant, "enabled": 1})
		if total_domains >= max_domains:
			frappe.throw(
				_("You have reached the maximum limit of {0} domains for the tenant.").format(
					frappe.bold(max_domains)
				)
			)

	def validate_is_verified(self) -> None:
		"""Validates the Is Verified field."""

		if not self.enabled:
			self.is_verified = 0

	@frappe.whitelist()
	def verify_dns_records(self, do_not_save: bool = False) -> bool:
		"""Verifies the DNS Records."""

		if not has_permission(self, "write"):
			frappe.throw(_("You do not have permission to verify DNS Records."))

		if not self._dns_records:
			return frappe.throw(_("Failed to fetch DNS Records."))

		failed_records = []
		for record in self._dns_records:
			if record["mandatory"] and not verify_dns_record(record["host"], record["type"], record["value"]):
				value = record["value"]
				if len(value) > 30:
					value = f"{value[:15]}...{value[-15:]}"

				failed_records.append(
					_("{0} record for {1} should have value {2}").format(
						frappe.bold(record["type"]), frappe.bold(record["host"]), frappe.bold(value)
					)
				)

		if not failed_records:
			self.is_verified = 1
			frappe.msgprint(_("DNS Records verified successfully."), indicator="green", alert=True)
		else:
			self.is_verified = 0
			frappe.msgprint(failed_records, title="DNS Verification Failed", as_list=True)

		if not do_not_save:
			self.save(ignore_permissions=True)

		return bool(self.is_verified)

	def clear_cache(self) -> None:
		"""Clears the Cache."""

		frappe.cache.hdel(f"domain|{self.name}", "tenant")
		frappe.cache.hdel(f"tenant|{self.tenant}", "domains")

	def _fetch_dns_records(self) -> list[dict]:
		"""Fetch DNS Records from the Mail Backend API."""

		cluster = get_cluster_for_tenant(self.tenant)
		backend_api = get_mail_backend_api("Mail Cluster", cluster)
		response = backend_api.request(method="GET", endpoint=f"/api/dns/records/{self.domain_name}")
		raise_for_status(response)

		return response.json()["data"]

	def _get_mail_cname_hostname(self, dns_records: list[dict]) -> str | None:
		"""Returns the CNAME hostname from the DNS records."""

		return next(
			(
				r["content"]
				for r in dns_records
				if r["type"] == "CNAME" and r["name"] == f"mail.{self.domain_name}."
			),
			None,
		)

	def _normalize_record(
		self, record: dict, spf_host: str, root_domain: str, hostname: str, cname_hostname: str | None
	) -> dict:
		"""Transform DNS record to standardized structure."""

		record["host"] = record.pop("name")
		record["value"] = (
			record.pop("content").replace(cname_hostname, hostname)
			if cname_hostname
			else record.pop("content")
		)

		if record["type"] == "TXT" and record["value"].startswith("v=spf1"):
			record["value"] = f"v=spf1 include:{spf_host}.{root_domain} ~all"

		if record["type"] == "MX":
			priority, record["value"] = record["value"].split(" ", 1)
			record["priority"] = cint(priority)
		elif record["type"] == "SRV":
			priority, weight, port, record["value"] = record["value"].split(" ", 3)
			record["priority"] = cint(priority)
			record["weight"] = cint(weight)
			record["port"] = cint(port)

		record["mandatory"] = int(
			(record["type"] == "CNAME" and record["host"] == f"mail.{self.domain_name}.")
			or (
				record["type"] == "TXT"
				and (
					record["value"].startswith("v=spf1")
					or record["host"] == f"_dmarc.{self.domain_name}."
					or record["host"].endswith(f"._domainkey.{self.domain_name}.")
				)
			)
		)

		return record

	def _should_skip_record(self, record: dict) -> bool:
		"""Skip redundant CNAME for root domain."""

		return (
			self.is_root_domain
			and record["type"] == "CNAME"
			and record["name"] == f"mail.{self.domain_name}."
			and record["name"] == record["content"]
		)


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Domain":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True

	if is_tenant_admin(doc.tenant, user):
		if ptype in ("read", "write"):
			return True

	return False


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	if has_role(user, "Mail Admin"):
		if tenant := get_tenant_for_user(user):
			return f"(`tabMail Domain`.`tenant` = {frappe.db.escape(tenant)})"

	if has_role(user, "Mail User"):
		if linked_domains := get_user_linked_domains(user):
			return f'(`tabMail Domain`.`domain_name` IN ({", ".join([frappe.db.escape(domain) for domain in linked_domains])}))'

	return "1=0"
