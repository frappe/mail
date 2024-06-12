# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from mail.utils import get_dns_record
from typing import Optional, TYPE_CHECKING
from frappe.model.document import Document
from mail.utils.agent import get_agent_client
from mail.mail.doctype.mail_settings.mail_settings import validate_mail_settings

if TYPE_CHECKING:
	from requests import Response


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
		self.validate_host()

	def on_update(self) -> None:
		self.update_server_dns_records()

	def on_trash(self) -> None:
		self.db_set("enabled", 0)
		self.update_server_dns_records()

	def validate_agent(self) -> None:
		"""Validates the agent and checks if the agent already exists."""

		if self.is_new() and frappe.db.exists("Mail Agent", self.agent):
			frappe.throw(
				_(
					"Mail Agent {0} already exists.".format(
						frappe.bold(self.agent),
					)
				)
			)

		if frappe.conf.developer_mode or frappe.session.user == "Administrator":
			return

		ipv4 = get_dns_record(self.agent, "A")
		ipv6 = get_dns_record(self.agent, "AAAA")

		self.ipv4 = ipv4[0].address if ipv4 else None
		self.ipv6 = ipv6[0].address if ipv6 else None

		if not self.ipv4 and not self.ipv6:
			frappe.throw(
				_(
					"An A or AAAA record not found for the agent {0}.".format(
						frappe.bold(self.agent),
					)
				)
			)

	def validate_enabled(self) -> None:
		"""Disables the agent if incoming and outgoing are disabled."""

		if self.enabled and not self.incoming and not self.outgoing:
			self.enabled = 0

	def validate_incoming_and_outgoing(self) -> None:
		"""Validates the incoming and outgoing fields."""

		if self.incoming and self.outgoing:
			frappe.throw(_("Incoming and Outgoing cannot be enabled at the same time."))

		if self.incoming:
			if not self.priority:
				frappe.throw(_("Priority is required for incoming agents."))

		if not self.is_new() and not self.outgoing:
			self.remove_from_linked_domains()

	def validate_host(self) -> None:
		"""Validates the host and converts it to lowercase."""

		if self.host:
			self.host = self.host.lower()

	def remove_from_linked_domains(self) -> None:
		"""Removes the agent from the linked domains."""

		DOMAIN = frappe.qb.DocType("Mail Domain")
		frappe.qb.update(DOMAIN).set(DOMAIN.outgoing_agent, None).where(
			DOMAIN.outgoing_agent == self.agent
		).run()

	def update_server_dns_records(self) -> None:
		"""Updates the DNS records on the server."""

		frappe.get_doc("Mail Settings").generate_dns_records(save=True)

	def request(
		self,
		method: str,
		path: str,
		data: Optional[dict] = None,
		timeout: int | tuple[int, int] = (60, 120),
	) -> "Response":
		"""Makes an HTTP request to the mail agent API."""

		url = f"{self.protocol}://{self.host or self.agent}/api/method/{path}"
		client = get_agent_client(self.agent)
		response = client.session.request(
			method=method, url=url, headers=client.headers, json=data, timeout=timeout
		)
		return response
