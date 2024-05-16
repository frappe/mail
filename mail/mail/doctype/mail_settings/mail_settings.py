# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import Optional
from frappe.utils import cint
from mail.utils import is_valid_host
from frappe.model.document import Document
from frappe.core.api.file import get_max_file_size


class MailSettings(Document):
	def validate(self) -> None:
		self.validate_root_domain_name()
		self.validate_spf_host()
		self.validate_postmaster()
		self.validate_default_dkim_selector()
		self.validate_default_dkim_bits()
		self.generate_dns_records()
		self.validate_outgoing_max_attachment_size()
		self.validate_outgoing_total_attachments_size()

	def validate_root_domain_name(self) -> None:
		"""Validates the Root Domain Name."""

		self.root_domain_name = self.root_domain_name.lower()

	def validate_spf_host(self) -> None:
		"""Validates the SPF Host."""

		self.spf_host = self.spf_host.lower()

		if not is_valid_host(self.spf_host):
			msg = _(
				"SPF Host {0} is invalid. It can be alphanumeric but should not contain spaces or special characters, excluding underscores.".format(
					frappe.bold(self.spf_host)
				)
			)
			frappe.throw(msg)

	def validate_postmaster(self) -> None:
		"""Validates the Postmaster."""

		if not frappe.db.exists("User", self.postmaster):
			frappe.throw(_("User {0} does not exist.").format(frappe.bold(self.postmaster)))
		elif not frappe.db.get_value("User", self.postmaster, "enabled"):
			frappe.throw(_("User {0} is disabled.").format(frappe.bold(self.postmaster)))
		elif not frappe.db.exists(
			"Has Role", {"parent": self.postmaster, "role": "Postmaster", "parenttype": "User"}
		):
			frappe.throw(
				_("User {0} does not have the Postmaster role.").format(
					frappe.bold(self.postmaster)
				)
			)

	def validate_default_dkim_selector(self) -> None:
		"""Validates the DKIM Selector."""

		self.default_dkim_selector = self.default_dkim_selector.lower()

		if not is_valid_host(self.default_dkim_selector):
			msg = _(
				"DKIM Selector {0} is invalid. It can be alphanumeric but should not contain spaces or special characters, excluding underscores.".format(
					frappe.bold(self.default_dkim_selector)
				)
			)
			frappe.throw(msg)

	def validate_default_dkim_bits(self) -> None:
		"""Validates the DKIM Bits."""

		if cint(self.default_dkim_bits) < 1024:
			frappe.throw(_("DKIM Bits must be greater than 1024."))

	def generate_dns_records(self, save: bool = False) -> None:
		"""Generates the DNS Records."""

		self.dns_records.clear()

		agents = frappe.db.get_all(
			"Mail Agent",
			filters={"enabled": 1, "outgoing": 1},
			fields=["name", "outgoing", "ipv4", "ipv6"],
			order_by="creation asc",
		)

		if agents:
			records = []
			outgoing_agents = []
			category = "Server Record"

			for agent in agents:
				if agent.outgoing:
					# A Record
					if agent.ipv4:
						records.append(
							{
								"category": category,
								"type": "A",
								"host": agent.name,
								"value": agent.ipv4,
								"ttl": self.default_ttl,
							}
						)

					# AAAA Record
					if agent.ipv6:
						records.append(
							{
								"category": category,
								"type": "AAAA",
								"host": agent.name,
								"value": agent.ipv6,
								"ttl": self.default_ttl,
							}
						)

					outgoing_agents.append(f"a:{agent.name}")

			# TXT Record
			if outgoing_agents:
				records.append(
					{
						"category": category,
						"type": "TXT",
						"host": f"{self.spf_host}.{self.root_domain_name}",
						"value": f"v=spf1 {' '.join(outgoing_agents)} ~all",
						"ttl": self.default_ttl,
					}
				)

			self.extend("dns_records", records)

		if save:
			self.save()

	def validate_outgoing_max_attachment_size(self) -> None:
		"""Validates the Outgoing Max Attachment Size."""

		max_file_size = cint(get_max_file_size() / 1024 / 1024)

		if self.outgoing_max_attachment_size > max_file_size:
			frappe.throw(
				_("{0} should be less than or equal to {1} MB.").format(
					frappe.bold("Max Attachment Size"), frappe.bold(max_file_size)
				)
			)

	def validate_outgoing_total_attachments_size(self) -> None:
		"""Validates the Outgoing Total Attachments Size."""

		if self.outgoing_max_attachment_size > self.outgoing_total_attachments_size:
			frappe.throw(
				_("{0} should be greater than or equal to {1}.").format(
					frappe.bold("Total Attachments Size"), frappe.bold("Max Attachment Size")
				)
			)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_postmaster(
	doctype: Optional[str] = None,
	txt: Optional[str] = None,
	searchfield: Optional[str] = None,
	start: Optional[int] = 0,
	page_len: Optional[int] = 20,
	filters: Optional[dict] = None,
) -> list:
	"""Returns the Postmaster."""

	USER = frappe.qb.DocType("User")
	HAS_ROLE = frappe.qb.DocType("Has Role")
	return (
		frappe.qb.from_(USER)
		.left_join(HAS_ROLE)
		.on(USER.name == HAS_ROLE.parent)
		.select(USER.name)
		.where(
			(USER.enabled == 1)
			& (USER.name.like(f"%{txt}%"))
			& (HAS_ROLE.role == "Postmaster")
			& (HAS_ROLE.parenttype == "User")
		)
	).run(as_dict=False)
