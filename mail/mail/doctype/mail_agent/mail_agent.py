# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from mail.utils import get_dns_record
from mail.utils.cache import delete_cache
from frappe.model.document import Document
from mail.mail.doctype.mail_settings.mail_settings import validate_mail_settings


class MailAgent(Document):
	def autoname(self) -> None:
		self.agent = self.agent.lower()
		self.name = self.agent

	def validate(self) -> None:
		if self.is_new():
			validate_mail_settings()

		self.validate_agent()
		self.validate_enabled()
		self.validate_incoming_and_outgoing()

	def on_update(self) -> None:
		self.update_server_dns_records()
		delete_cache("incoming_mail_agents")
		delete_cache("outgoing_mail_agents")

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Agents."))

		self.db_set("enabled", 0)
		self.update_server_dns_records()
		self.remove_from_linked_domains()

	def validate_agent(self) -> None:
		"""Validates the agent and fetches the IP addresses."""

		if self.is_new() and frappe.db.exists("Mail Agent", self.agent):
			frappe.throw(
				_(
					"Mail Agent {0} already exists.".format(
						frappe.bold(self.agent),
					)
				)
			)

		ipv4 = get_dns_record(self.agent, "A")
		ipv6 = get_dns_record(self.agent, "AAAA")

		self.ipv4 = ipv4[0].address if ipv4 else None
		self.ipv6 = ipv6[0].address if ipv6 else None

	def validate_enabled(self) -> None:
		"""Disables the agent if incoming and outgoing are disabled."""

		if self.enabled and not self.incoming and not self.outgoing:
			self.enabled = 0

	def validate_incoming_and_outgoing(self) -> None:
		"""Validates the incoming and outgoing fields."""

		if self.incoming and self.outgoing:
			frappe.throw(_("Incoming and Outgoing cannot be enabled at the same time."))

		if self.incoming:
			if not self.group:
				frappe.throw(_("Group is required for incoming agent."))

			if self.enabled and not frappe.db.get_value(
				"Mail Agent Group", self.group, "enabled"
			):
				frappe.throw(_("Mail Agent Group {0} is disabled.".format(frappe.bold(self.group))))
		elif self.outgoing:
			self.group = None

		if not self.is_new() and not self.outgoing:
			self.remove_from_linked_domains()

	def remove_from_linked_domains(self) -> None:
		"""Removes the agent from the linked domains."""

		DOMAIN = frappe.qb.DocType("Mail Domain")
		frappe.qb.update(DOMAIN).set(DOMAIN.outgoing_agent, None).where(
			DOMAIN.outgoing_agent == self.agent
		).run()

	def update_server_dns_records(self) -> None:
		"""Updates the DNS Records of the server."""

		frappe.get_doc("Mail Settings").generate_dns_records(save=True)
