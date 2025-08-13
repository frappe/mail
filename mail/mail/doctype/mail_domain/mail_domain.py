# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from functools import cached_property

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.backend import MailBackendDomainManager, get_mail_backend_api
from mail.jmap import raise_for_status
from mail.mail.doctype.dkim_key.dkim_key import create_dkim_key
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
		"""Fetches the DNS Records for the Mail Domain."""

		if not self.is_new() and self.enabled:
			try:
				cluster = get_cluster_for_tenant(self.tenant)
				backend_api = get_mail_backend_api("Mail Cluster", cluster)
				response = backend_api.request(method="GET", endpoint=f"/api/dns/records/{self.domain_name}")
				raise_for_status(response)
				dns_records = response.json()["data"]

				mail_settings = frappe.get_cached_doc("Mail Settings")
				hostname = f"{frappe.db.get_value('Mail Cluster', cluster, 'hostname')}."
				_hostname = next(
					(
						r["content"]
						for r in dns_records
						if r["type"] == "CNAME" and r["name"] == f"mail.{self.domain_name}."
					),
					None,
				)

				cleaned_records = []
				for record in dns_records:
					record["host"] = record.pop("name")
					record["value"] = (
						record.pop("content").replace(_hostname, hostname)
						if _hostname
						else record.pop("content")
					)

					if (
						self.is_root_domain
						and record["type"] == "CNAME"
						and record["host"] == f"mail.{self.domain_name}."
						and record["host"] == record["value"]
					):
						continue

					if record["type"] == "TXT" and record["value"].startswith("v=spf1"):
						record[
							"value"
						] = f"v=spf1 include:{mail_settings.spf_host}.{mail_settings.root_domain_name} ~all"

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

					cleaned_records.append(record)

				return sorted(cleaned_records, key=lambda x: (x["mandatory"] == 0, x["type"], x["host"]))
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
		MailBackendDomainManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).create(self.domain_name)

	def on_update(self) -> None:
		self.clear_cache()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Domain."))

		self.clear_cache()
		MailBackendDomainManager("Mail Cluster", get_cluster_for_tenant(self.tenant)).delete(self.domain_name)

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
