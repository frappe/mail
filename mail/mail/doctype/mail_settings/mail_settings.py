# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document
from mail.utils.validation import is_valid_host
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

		if not self.postmaster:
			return

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

		records = []
		self.dns_records.clear()
		category = "Server Record"

		agents = frappe.db.get_all(
			"Mail Agent",
			filters={"enabled": 1},
			fields=["name", "incoming", "outgoing", "ipv4", "ipv6"],
			order_by="creation asc",
		)
		agent_groups = frappe.db.get_all(
			"Mail Agent Group",
			filters={"enabled": 1},
			fields=["name", "priority", "ipv4", "ipv6"],
			order_by="creation asc",
		)

		if agents:
			outgoing_agents = []

			for agent in agents:
				if agent.outgoing:
					outgoing_agents.append(f"a:{agent.name}")

				# A Record (Agent)
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

				# AAAA Record (Agent)
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

			# TXT Record (Agent)
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

		if agent_groups:
			for group in agent_groups:
				# A Record (Agent Group)
				if group.ipv4:
					records.append(
						{
							"category": category,
							"type": "A",
							"host": group.name,
							"value": group.ipv4,
							"ttl": self.default_ttl,
						}
					)

				# AAAA Record (Agent Group)
				if group.ipv6:
					records.append(
						{
							"category": category,
							"type": "AAAA",
							"host": group.name,
							"value": group.ipv6,
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
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
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


def validate_mail_settings() -> None:
	"""Validates the mandatory fields in the Mail Settings."""

	mail_settings = frappe.get_doc("Mail Settings")
	mandatory_fields = [
		"root_domain_name",
		"spf_host",
		"default_dkim_selector",
		"default_dkim_bits",
		"default_ttl",
	]

	for field in mandatory_fields:
		if not mail_settings.get(field):
			field_label = frappe.get_meta("Mail Settings").get_label(field)
			frappe.throw(
				_("Please set the {0} in the Mail Settings.".format(frappe.bold(field_label)))
			)
