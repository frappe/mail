# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from mail.utils import get_dns_record
from frappe.model.document import Document


class MailAgentGroup(Document):
	def autoname(self) -> None:
		self.host = self.host.lower()
		self.name = self.host

	def validate(self):
		self.validate_mail_agent_group()
		self.validate_agents()

	def on_update(self) -> None:
		self.update_server_dns_records()

	def validate_mail_agent_group(self):
		"""Validates the mail agent group and fetches the IP addresses."""

		if self.is_new() and frappe.db.exists("Mail Agent Group", self.host):
			frappe.throw(
				_(
					"Mail Agent Group {0} already exists.".format(
						frappe.bold(self.host),
					)
				)
			)

		ipv4 = get_dns_record(self.host, "A")
		ipv6 = get_dns_record(self.host, "AAAA")

		self.ipv4 = ipv4[0].address if ipv4 else None
		self.ipv6 = ipv6[0].address if ipv6 else None

	def validate_agents(self):
		"""Validates the agents."""

		if not self.is_new() and not self.enabled:
			MA = frappe.qb.DocType("Mail Agent")
			(
				frappe.qb.update(MA)
				.set("enabled", 0)
				.where((MA.enabled == 1) & (MA.group == self.name))
			).run()

	def update_server_dns_records(self) -> None:
		"""Updates the DNS Records of the server."""

		frappe.get_doc("Mail Settings").refresh_dns_records(save=True)
