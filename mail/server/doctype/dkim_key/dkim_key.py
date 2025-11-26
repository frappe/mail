# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import Literal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, random_string

from mail.backend import MailBackendDKIMManager
from mail.server.doctype.dns_record.dns_record import create_or_update_dns_record
from mail.utils import generate_dkim_keys, get_dkim_host
from mail.utils.cache import get_cluster_for_tenant, get_tenant_for_domain


class DKIMKey(Document):
	def autoname(self) -> None:
		self.name = f"{self.domain_name.replace('.', '-')}-{random_string(length=10)}"

	def validate(self) -> None:
		self.validate_rsa_key_size()

		if self.is_new():
			self.generate_dkim_keys()

	def on_update(self) -> None:
		if self.enabled:
			if self.has_value_changed("enabled"):
				self.create_or_update_dns_record()
				self.disable_existing_dkim_keys()
				MailBackendDKIMManager(
					"Mail Cluster", get_cluster_for_tenant(get_tenant_for_domain(self.domain_name))
				).create(self.domain_name, self.get_password("rsa_private_key"))
		elif self.has_value_changed("enabled"):
			MailBackendDKIMManager(
				"Mail Cluster", get_cluster_for_tenant(get_tenant_for_domain(self.domain_name))
			).delete(self.domain_name)

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete DKIM Key."))

		if self.enabled:
			MailBackendDKIMManager(
				"Mail Cluster", get_cluster_for_tenant(get_tenant_for_domain(self.domain_name))
			).delete(self.domain_name)

	def validate_rsa_key_size(self) -> None:
		"""Validates the Key Size."""

		if not self.rsa_key_size:
			self.rsa_key_size = frappe.db.get_single_value(
				"Mail Settings", "default_dkim_rsa_key_size", cache=True
			)

	def generate_dkim_keys(self) -> None:
		"""Generates the DKIM Keys."""

		self.rsa_private_key, self.rsa_public_key = generate_dkim_keys("rsa-sha256", cint(self.rsa_key_size))

	def create_or_update_dns_record(self) -> None:
		"""Creates or Updates the DNS Record."""

		create_or_update_dns_record(
			host=f"{get_dkim_host(self.domain_name, 'rsa')}._domainkey",
			type="TXT",
			value=f"v=DKIM1; k=rsa; h=sha256; p={self.rsa_public_key}",
			ttl=300,
			category="Sending Record",
			attached_to_doctype=self.doctype,
			attached_to_docname=self.name,
		)

	def disable_existing_dkim_keys(self) -> None:
		"""Disables the existing DKIM Keys."""

		filters = {"enabled": 1, "domain_name": self.domain_name, "name": ["!=", self.name]}
		for dkim_key in frappe.db.get_all("DKIM Key", filters, pluck="name"):
			dkim_key = frappe.get_doc("DKIM Key", dkim_key)
			dkim_key.enabled = 0
			dkim_key.save(ignore_permissions=True)


def create_dkim_key(domain_name: str, rsa_key_size: int | None = None) -> "DKIMKey":
	"""Creates a DKIM Key document."""

	doc = frappe.new_doc("DKIM Key")
	doc.enabled = 1
	doc.domain_name = domain_name
	doc.rsa_key_size = rsa_key_size
	doc.flags.ignore_links = True
	doc.insert(ignore_permissions=True)

	return doc
