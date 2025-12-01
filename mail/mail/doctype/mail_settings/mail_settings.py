# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from mail.server.doctype.dns_record.dns_record import get_dns_provider


class MailSettings(Document):
	def validate(self) -> None:
		self.validate_root_domain_name()
		self.validate_dns_provider()
		self.validate_personal_signup_domains()

	def on_update(self) -> None:
		self.clear_cache()

		if self.has_value_changed("root_domain_name"):
			self.handle_root_domain_change()

	def validate_root_domain_name(self) -> None:
		"""Validates the Root Domain Name."""

		self.root_domain_name = self.root_domain_name.lower()

	def validate_dns_provider(self) -> None:
		"""Validates the DNS Provider."""

		if not self.dns_provider:
			return

		match self.dns_provider:
			case "AmazonRoute53":
				if not self.dns_provider_access_key or not self.dns_provider_access_secret:
					frappe.throw(_("Please set the DNS Provider Access Key and Secret."))

			case "DigitalOcean" | "Cloudflare" | "Hetzner" | "Linode" | "Namecheap":
				if not self.dns_provider_token:
					frappe.throw(_("Please set the DNS Provider Token."))
				elif self.dns_provider == "Namecheap":
					if not self.dns_provider_username or not self.dns_provider_client_ip:
						frappe.throw(_("Please set the DNS Provider Username and Client IP."))

			case "GoDaddy":
				if not self.dns_provider_key or not self.dns_provider_secret:
					frappe.throw(_("Please set the DNS Provider Key and Secret."))

		verify_dns_provider = (
			self.has_value_changed("root_domain_name")
			or self.has_value_changed("dns_provider")
			or self.has_value_changed("dns_provider_access_key")
			or self.has_value_changed("dns_provider_access_secret")
			or self.has_value_changed("dns_provider_token")
			or self.has_value_changed("dns_provider_username")
			or self.has_value_changed("dns_provider_client_ip")
			or self.has_value_changed("dns_provider_key")
			or self.has_value_changed("dns_provider_secret")
		)

		if verify_dns_provider:
			dns_provider = get_dns_provider(self)
			dns_provider.read_dns_records("MX")

	def validate_personal_signup_domains(self) -> None:
		"""Validates the Personal Signup Domains."""

		if not self.personal_signup_domains:
			return

		principals = frappe.db.get_all(
			"Mail Principal Binding",
			{"name": ["in", [d.principal for d in self.personal_signup_domains]]},
			["principal_name", "is_verified", "tenant"],
		)

		if not principals:
			self.personal_signup_domains = []
			return

		for principal in principals:
			if not frappe.db.get_value("Mail Tenant", principal.tenant, "allow_personal_signup"):
				frappe.throw(
					_("Personal Signup is not allowed for the domain {0}.").format(
						frappe.bold(principal.principal_name)
					)
				)
			elif not principal.is_verified:
				frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(principal.principal_name)))

	def handle_root_domain_change(self) -> None:
		"""Resets DNS Record verification and notifies user after root domain change."""

		frappe.db.set_value("DNS Record", {"is_verified": 1}, "is_verified", 0)

		if self.has_value_changed("root_domain_name"):
			dns_record_list_link = f'<a href="/app/dns-record">{_("DNS Records")}</a>'
			frappe.msgprint(
				_("Please verify the {0} for the new {1} to ensure proper email authentication.").format(
					dns_record_list_link, frappe.bold("Root Domain Name")
				)
			)

	def clear_cache(self) -> None:
		"""Clears the Cache."""

		frappe.cache.delete_value("mail-settings")


def validate_mail_settings() -> None:
	"""Validates the mandatory fields in the Mail Settings."""

	mail_settings = frappe.get_doc("Mail Settings")
	mandatory_fields = ["root_domain_name"]

	for field in mandatory_fields:
		if not mail_settings.get(field):
			field_label = frappe.get_meta("Mail Settings").get_label(field)
			frappe.throw(_("Please set the {0} in the Mail Settings.").format(frappe.bold(field_label)))
