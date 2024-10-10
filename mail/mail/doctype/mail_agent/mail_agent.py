# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from mail.utils import get_dns_record
from frappe.model.document import Document
from mail.mail.doctype.dns_record.dns_record import create_or_update_dns_record
from mail.mail.doctype.mail_settings.mail_settings import validate_mail_settings


class MailAgent(Document):
	def autoname(self) -> None:
		self.agent = self.agent.lower()
		self.name = self.agent

	def validate(self) -> None:
		if self.is_new():
			validate_mail_settings()

		self.validate_agent()

	def on_update(self) -> None:
		if self.type == "Outbound":
			create_or_update_spf_dns_record()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Agent."))

		self.db_set("enabled", 0)
		create_or_update_spf_dns_record()

	def validate_agent(self) -> None:
		"""Validates the agent and fetches the IP addresses."""

		if self.is_new() and frappe.db.exists("Mail Agent", self.agent):
			frappe.throw(_("Mail Agent {0} already exists.").format(frappe.bold(self.agent)))

		ipv4 = get_dns_record(self.agent, "A")
		ipv6 = get_dns_record(self.agent, "AAAA")

		self.ipv4 = ipv4[0].address if ipv4 else None
		self.ipv6 = ipv6[0].address if ipv6 else None


def create_or_update_spf_dns_record(spf_host: str | None = None) -> None:
	"""Refreshes the SPF DNS Record."""

	mail_settings = frappe.get_single("Mail Settings")
	spf_host = spf_host or mail_settings.spf_host
	outbound_agents = frappe.db.get_all(
		"Mail Agent",
		filters={"enabled": 1, "type": "Outbound"},
		pluck="agent",
		order_by="agent asc",
	)

	if not outbound_agents:
		if spf_dns_record := frappe.db.exists(
			"DNS Record", {"host": spf_host, "type": "TXT"}
		):
			frappe.delete_doc("DNS Record", spf_dns_record, ignore_permissions=True)
			return

	create_or_update_dns_record(
		host=spf_host,
		type="TXT",
		value=f"v=spf1 {' '.join(outbound_agents)} ~all",
		ttl=mail_settings.default_ttl,
		category="Server Record",
	)
