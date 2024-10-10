# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document
from mail.utils.user import has_role, is_system_manager
from mail.mail.doctype.dkim_key.dkim_key import create_dkim_key
from mail.utils.cache import delete_cache, get_user_domains, get_root_domain_name
from mail.mail.doctype.mailbox.mailbox import (
	create_dmarc_mailbox,
	create_postmaster_mailbox,
)


class MailDomain(Document):
	def autoname(self) -> None:
		self.domain_name = self.domain_name.strip().lower()
		self.name = self.domain_name

	def validate(self) -> None:
		self.validate_dkim_key_size()
		self.validate_newsletter_retention()
		self.validate_subdomain()
		self.validate_root_domain()

		if self.is_new() or self.has_value_changed("dkim_key_size"):
			create_dkim_key(self.domain_name, cint(self.dkim_key_size))
			self.refresh_dns_records()
		elif not self.enabled:
			self.is_verified = 0

	def after_insert(self) -> None:
		if self.is_root_domain:
			create_postmaster_mailbox(self.domain_name)

		create_dmarc_mailbox(self.domain_name)

	def on_update(self) -> None:
		delete_cache(f"user|{self.domain_owner}")

	def validate_dkim_key_size(self) -> None:
		"""Validates the DKIM Key Size."""

		if self.dkim_key_size:
			if cint(self.dkim_key_size) < 1024:
				frappe.throw(_("DKIM Key Size must be greater than 1024."))
		else:
			self.dkim_key_size = frappe.db.get_single_value(
				"Mail Settings", "default_dkim_key_size", cache=True
			)

	def validate_newsletter_retention(self) -> None:
		"""Validates the Newsletter Retention."""

		if self.newsletter_retention:
			if self.newsletter_retention < 1:
				frappe.throw(_("Newsletter Retention must be greater than 0."))

			max_newsletter_retention = frappe.db.get_single_value(
				"Mail Settings", "max_newsletter_retention", cache=True
			)
			if self.newsletter_retention > max_newsletter_retention:
				frappe.throw(
					_("Newsletter Retention must be less than or equal to {0}.").format(
						frappe.bold(max_newsletter_retention)
					)
				)
		else:
			self.newsletter_retention = frappe.db.get_single_value(
				"Mail Settings", "default_newsletter_retention", cache=True
			)

	def validate_subdomain(self) -> None:
		"""Validates if the domain is a subdomain."""

		if len(self.domain_name.split(".")) > 2:
			self.is_subdomain = 1

	def validate_root_domain(self) -> None:
		"""Validates if the domain is the root domain."""

		self.is_root_domain = 1 if self.domain_name == get_root_domain_name() else 0

	@frappe.whitelist()
	def refresh_dns_records(self, save: bool = False) -> None:
		"""Refreshes the DNS Records."""

		self.is_verified = 0
		self.dns_records.clear()
		mail_settings = frappe.get_single("Mail Settings")

		sending_records = self.get_sending_records(
			mail_settings.root_domain_name, mail_settings.spf_host, mail_settings.default_ttl
		)
		receiving_records = self.get_receiving_records(mail_settings.default_ttl)

		self.extend("dns_records", sending_records)
		self.extend("dns_records", receiving_records)

		if save:
			self.save()

	def get_sending_records(
		self, root_domain_name: str, spf_host: str, ttl: int
	) -> list[dict]:
		"""Returns the Sending Records."""

		records = []
		type = "TXT"
		category = "Sending Record"

		# SPF Record
		records.append(
			{
				"category": category,
				"type": type,
				"host": self.domain_name,
				"value": f"v=spf1 include:{spf_host}.{root_domain_name} ~all",
				"ttl": ttl,
			},
		)

		# DMARC Record
		dmarc_value = (
			f"v=DMARC1; p=reject; rua=mailto:dmarc@{self.domain_name}; ruf=mailto:dmarc@{self.domain_name}; fo=1; adkim=s; aspf=s; pct=100;"
			if self.is_root_domain
			else f"v=DMARC1; p=reject; rua=mailto:dmarc@{self.domain_name}; ruf=mailto:dmarc@{self.domain_name}; fo=1; adkim=r; aspf=r; pct=100;"
		)
		records.append(
			{
				"category": category,
				"type": type,
				"host": f"_dmarc.{self.domain_name}",
				"value": dmarc_value,
				"ttl": ttl,
			}
		)

		return records

	def get_receiving_records(self, ttl: int) -> list[dict]:
		"""Returns the Receiving Records."""

		records = []
		if inbound_agents := frappe.db.get_all(
			"Mail Agent",
			filters={"enabled": 1, "type": "Inbound"},
			fields=["agent", "priority"],
			order_by="priority asc",
		):
			for inbound_agent in inbound_agents:
				records.append(
					{
						"category": "Receiving Record",
						"type": "MX",
						"host": self.domain_name,
						"value": f"{inbound_agent.agent.split(':')[0]}.",
						"priority": inbound_agent.priority,
						"ttl": ttl,
					}
				)

		return records

	@frappe.whitelist()
	def verify_dns_records(self, save: bool = False) -> None:
		"""Verifies the DNS Records."""

		from mail.utils import verify_dns_record

		self.is_verified = 1

		for record in self.dns_records:
			if verify_dns_record(record.host, record.type, record.value):
				record.is_verified = 1
				frappe.msgprint(
					_("Row #{0}: Verified {1}:{2} record.").format(
						frappe.bold(record.idx), frappe.bold(record.type), frappe.bold(record.host)
					),
					indicator="green",
					alert=True,
				)
			else:
				record.is_verified = 0
				self.is_verified = 0
				frappe.msgprint(
					_("Row #{0}: Could not verify {1}:{2} record.").format(
						frappe.bold(record.idx), frappe.bold(record.type), frappe.bold(record.host)
					),
					indicator="orange",
					alert=True,
				)

		if save:
			self.save()


def has_permission(doc: "Document", ptype: str, user: str) -> bool:
	if doc.doctype != "Mail Domain":
		return False

	return is_system_manager(user) or (user == doc.domain_owner)


def get_permission_query_condition(user: str | None = None) -> str:
	conditions = []

	if not user:
		user = frappe.session.user

	if not is_system_manager(user):
		if has_role(user, "Domain Owner"):
			conditions.append(f"(`tabMail Domain`.`domain_owner` = {frappe.db.escape(user)})")

		if has_role(user, "Mailbox User"):
			if domains := ", ".join(repr(d) for d in get_user_domains(user)):
				conditions.append(f"(`tabMail Domain`.`domain_name` IN ({domains}))")

	return " OR ".join(conditions)
