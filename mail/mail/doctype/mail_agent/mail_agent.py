# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from mail.utils import get_dns_record
from frappe.model.document import Document
from mail.utils.agent import get_agent_rabbitmq_connection
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
		self.validate_rmq_host()

	def on_update(self) -> None:
		self.update_server_dns_records()
		frappe.cache.delete_value("outgoing_mail_agents")

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

	def validate_rmq_host(self) -> None:
		"""Validates the rmq_host and converts it to lowercase."""

		if self.rmq_host:
			self.rmq_host = self.rmq_host.lower()

	def remove_from_linked_domains(self) -> None:
		"""Removes the agent from the linked domains."""

		DOMAIN = frappe.qb.DocType("Mail Domain")
		frappe.qb.update(DOMAIN).set(DOMAIN.outgoing_agent, None).where(
			DOMAIN.outgoing_agent == self.agent
		).run()

	def update_server_dns_records(self) -> None:
		"""Updates the DNS Records of the server."""

		frappe.get_doc("Mail Settings").generate_dns_records(save=True)

	@frappe.whitelist()
	def test_rabbitmq_connection(self) -> None:
		"""Tests the connection to the RabbitMQ server."""

		try:
			rmq = get_agent_rabbitmq_connection(self.agent)
			rmq._disconnect()
			frappe.msgprint(_("Connection Successful"), alert=True, indicator="green")
		except Exception as e:
			messages = []
			for error in e.args:
				if not isinstance(error, str):
					error = error.exception

				messages.append("{}: {}".format(frappe.bold(e.__class__.__name__), error))

			as_list = True
			if len(messages) == 1:
				messages = messages[0]
				as_list = False

			frappe.msgprint(messages, _("Connection Failed"), as_list=as_list, indicator="red")
