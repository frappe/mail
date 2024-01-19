# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from mail.utils import Utils
from frappe.model.document import Document


class FMServer(Document):
	def autoname(self) -> None:
		self.server = self.server.lower()
		self.name = self.server

	def validate(self) -> None:
		self.validate_server()
		self.validate_incoming()
		self.validate_outgoing()
		self.validate_host()

	def on_update(self) -> None:
		self.update_server_dns_records()

	def on_trash(self) -> None:
		self.db_set("is_active", 0)
		self.update_server_dns_records()

	def validate_server(self) -> None:
		ipv4 = Utils.get_dns_record(self.server, "A")
		ipv6 = Utils.get_dns_record(self.server, "AAAA")

		self.ipv4 = ipv4[0].address if ipv4 else None
		self.ipv6 = ipv6[0].address if ipv6 else None

		if not ipv4 and not ipv6:
			frappe.throw(
				_(
					"An A or AAAA record not found for the server {0}.".format(
						frappe.bold(self.server),
					)
				)
			)

	def validate_incoming(self) -> None:
		if self.is_incoming:
			if self.priority:
				if frappe.db.get_all(
					"FM Server", filters={"priority": self.priority, "name": ["!=", self.name]}
				):
					frappe.throw(
						_(
							"Priority {0} is already assigned to another server.".format(
								frappe.bold(self.priority),
							)
						)
					)
			else:
				frappe.throw(_("Priority is required for incoming servers."))

	def validate_outgoing(self) -> None:
		if self.is_outgoing:
			if self.port:
				if not Utils.is_port_open(self.server, self.port):
					frappe.throw(
						_(
							"Port {0} is not open on the server {1}.".format(
								frappe.bold(self.port),
								frappe.bold(self.server),
							)
						)
					)
			else:
				frappe.throw(_("Port is required for outgoing servers."))

	def validate_host(self) -> None:
		if hasattr(self, "host") and self.host:
			self.host = self.host.lower()

			if self.host != "localhost" and not Utils.is_valid_ip(self.host):
				frappe.throw(
					_(
						"Unable to connect to the host {0}.".format(
							frappe.bold(self.host),
						)
					)
				)

	def update_server_dns_records(self) -> None:
		frappe.get_doc("FM Settings").generate_dns_records(save=True)
