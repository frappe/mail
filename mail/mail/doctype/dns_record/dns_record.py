# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now
from frappe.model.document import Document
from mail.mail.doctype.dns_record.dns_provider import DNSProvider


class DNSRecord(Document):
	def validate(self) -> None:
		if self.is_new():
			self.validate_duplicate_record()
			self.validate_ttl()

	def on_update(self) -> None:
		if self.has_value_changed("value") or self.has_value_changed("ttl"):
			self.is_verified = 0
			self.create_or_update_record_in_dns_provider()

	def on_trash(self) -> None:
		self.delete_record_from_dns_provider()

	def validate_duplicate_record(self) -> None:
		"""Validates if a duplicate DNS Record exists"""

		if frappe.db.exists(
			"DNS Record",
			{"host": self.host, "type": self.type, "name": ["!=", self.name]},
		):
			frappe.throw(
				_("DNS Record with the same host and type already exists."),
				title=_("Duplicate Record"),
			)

	def validate_ttl(self) -> None:
		"""Validates the TTL value"""

		if not self.ttl:
			self.ttl = frappe.db.get_single_value("Mail Settings", "default_ttl", cache=True)

	def create_or_update_record_in_dns_provider(self) -> None:
		"""Creates or Updates the DNS Record in the DNS Provider"""

		mail_settings = frappe.get_single("Mail Settings")

		if not mail_settings.dns_provider or not mail_settings.dns_provider_token:
			return

		dns_provider = DNSProvider(
			provider=mail_settings.dns_provider,
			token=mail_settings.get_password("dns_provider_token"),
		)
		dns_provider.create_or_update_dns_record(
			domain=mail_settings.root_domain_name,
			type=self.type,
			host=self.host,
			value=self.value,
			ttl=self.ttl,
		)

	def delete_record_from_dns_provider(self) -> None:
		"""Deletes the DNS Record from the DNS Provider"""

		mail_settings = frappe.get_single("Mail Settings")

		if not mail_settings.dns_provider or not mail_settings.dns_provider_token:
			return

		dns_provider = DNSProvider(
			provider=mail_settings.dns_provider,
			token=mail_settings.get_password("dns_provider_token"),
		)
		dns_provider.delete_dns_record_if_exists(
			domain=mail_settings.root_domain_name, type=self.type, host=self.host
		)

	def get_fqdn(self) -> str:
		"""Returns the Fully Qualified Domain Name"""

		from mail.utils.cache import get_root_domain_name

		return f"{self.host}.{get_root_domain_name()}"

	@frappe.whitelist()
	def verify_dns_record(self, save: bool = False) -> None:
		"""Verifies the DNS Record"""

		from mail.utils import verify_dns_record

		self.is_verified = 0
		self.last_checked_at = now()
		if verify_dns_record(self.get_fqdn(), self.type, self.value):
			self.is_verified = 1
			frappe.msgprint(
				_("Verified {0}:{1} record.").format(
					frappe.bold(self.get_fqdn()), frappe.bold(self.type)
				),
				indicator="green",
				alert=True,
			)

		if save:
			self.save()


def create_or_update_dns_record(
	host: str,
	type: str,
	value: str,
	ttl: int | None = None,
	priority: int | None = None,
	category: str | None = None,
	attached_to_doctype: str | None = None,
	attached_to_docname: str | None = None,
) -> "DNSRecord":
	"""Creates or updates a DNS Record"""

	if dns_record := frappe.db.exists("DNS Record", {"host": host, "type": type}):
		dns_record = frappe.get_doc("DNS Record", dns_record)
	else:
		dns_record = frappe.new_doc("DNS Record")
		dns_record.host = host
		dns_record.type = type
		dns_record.attached_to_doctype = attached_to_doctype
		dns_record.attached_to_docname = attached_to_docname

	dns_record.value = value
	dns_record.ttl = ttl
	dns_record.priority = priority
	dns_record.category = category
	dns_record.save()

	return dns_record


def after_doctype_insert() -> None:
	frappe.db.add_unique("DNS Record", ["host", "type"])
