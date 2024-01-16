# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from mail.utils import Utils
from frappe.utils import cint
from frappe.model.document import Document


class FMSettings(Document):
	def validate(self) -> None:
		self.validate_primary_domain_name()
		self.validate_spf_host()
		self.validate_outgoing_servers()
		self.validate_incoming_servers()
		self.validate_default_dkim_selector()
		self.validate_default_dkim_bits()
		self.generate_dns_records()

	def validate_primary_domain_name(self) -> None:
		self.primary_domain_name = self.primary_domain_name.lower()

		if not Utils.is_valid_domain(self.primary_domain_name):
			frappe.throw(
				_(
					"Primary Domain Name {0} is invalid.".format(frappe.bold(self.primary_domain_name))
				)
			)

	def validate_spf_host(self) -> None:
		self.spf_host = self.spf_host.lower()

		if not Utils.is_valid_host(self.spf_host):
			msg = _(
				"SPF Host {0} is invalid. It can be alphanumeric but should not contain spaces or special characters, excluding underscores.".format(
					frappe.bold(self.spf_host)
				)
			)
			frappe.throw(msg)

	def validate_outgoing_servers(self) -> None:
		server_list = []

		for outgoing_server in self.outgoing_servers:
			outgoing_server.server = outgoing_server.server.lower()

			if outgoing_server.server in server_list:
				frappe.throw(
					_(
						"{0} Row #{1}: Duplicate server {2}.".format(
							frappe.bold("Outgoing Server"),
							outgoing_server.idx,
							frappe.bold(outgoing_server.server),
						)
					)
				)

			server_list.append(outgoing_server.server)

			public_ipv4 = Utils.get_dns_record(outgoing_server.server, "A")
			public_ipv6 = Utils.get_dns_record(outgoing_server.server, "AAAA")

			outgoing_server.public_ipv4 = public_ipv4[0].address if public_ipv4 else None
			outgoing_server.public_ipv6 = public_ipv6[0].address if public_ipv6 else None

			if not public_ipv4 and not public_ipv6:
				frappe.throw(
					_(
						"{0} Row #{1}: An A or AAAA record not found for the server {2}.".format(
							frappe.bold("Outgoing Server"),
							outgoing_server.idx,
							frappe.bold(outgoing_server.server),
						)
					)
				)

			if not Utils.is_port_open(outgoing_server.server, outgoing_server.port):
				frappe.throw(
					_(
						"{0} Row #{1}: Port {2} is not open on the server {3}.".format(
							frappe.bold("Outgoing Server"),
							outgoing_server.idx,
							frappe.bold(outgoing_server.port),
							frappe.bold(outgoing_server.server),
						)
					)
				)

	def validate_incoming_servers(self) -> None:
		server_list = []
		priority_list = []
		outgoing_servers = [
			outgoing_server.server for outgoing_server in self.outgoing_servers
		]

		if self.incoming_servers:
			for incoming_server in self.incoming_servers:
				incoming_server.server = incoming_server.server.lower()

				if incoming_server.server in server_list:
					frappe.throw(
						_(
							"{0} Row #{1}: Duplicate server {2}.".format(
								frappe.bold("Incoming Server"),
								incoming_server.idx,
								frappe.bold(incoming_server.server),
							)
						)
					)

				if incoming_server.priority in priority_list:
					frappe.throw(
						_(
							"{0} Row #{1}: Duplicate priority {2}.".format(
								frappe.bold("Incoming Server"),
								incoming_server.idx,
								frappe.bold(incoming_server.priority),
							)
						)
					)

				server_list.append(incoming_server.server)
				priority_list.append(incoming_server.priority)

				if incoming_server.server not in outgoing_servers:
					if not Utils.get_dns_record(
						incoming_server.server, "A"
					) or not Utils.get_dns_record(incoming_server.server, "AAAA"):
						frappe.throw(
							_(
								"{0} Row #{1}: An A or AAAA record not found for the server {2}.".format(
									frappe.bold("Incoming Server"),
									incoming_server.idx,
									frappe.bold(incoming_server.server),
								)
							)
						)

	def validate_default_dkim_selector(self) -> None:
		self.default_dkim_selector = self.default_dkim_selector.lower()

		if not Utils.is_valid_host(self.default_dkim_selector):
			msg = _(
				"DKIM Selector {0} is invalid. It can be alphanumeric but should not contain spaces or special characters, excluding underscores.".format(
					frappe.bold(self.default_dkim_selector)
				)
			)
			frappe.throw(msg)

	def validate_default_dkim_bits(self) -> None:
		if cint(self.default_dkim_bits) < 1024:
			frappe.throw(_("DKIM Bits must be greater than 1024."))

	def generate_dns_records(self) -> None:
		self.dns_records.clear()

		records = []
		outgoing_servers = []
		category = "Server Record"

		for outgoing_server in self.outgoing_servers:
			# A Record
			if outgoing_server.public_ipv4:
				records.append(
					{
						"category": category,
						"type": "A",
						"host": outgoing_server.server,
						"value": outgoing_server.public_ipv4,
						"ttl": self.default_ttl,
					}
				)

			# AAAA Record
			if outgoing_server.public_ipv6:
				records.append(
					{
						"category": category,
						"type": "AAAA",
						"host": outgoing_server.server,
						"value": outgoing_server.public_ipv6,
						"ttl": self.default_ttl,
					}
				)

			outgoing_servers.append(f"a:{outgoing_server.server}")

		# TXT Record
		records.append(
			{
				"category": category,
				"type": "TXT",
				"host": f"{self.spf_host}.{self.primary_domain_name}",
				"value": f"v=spf1 {' '.join(outgoing_servers)} ~all",
				"ttl": self.default_ttl,
			}
		)

		self.extend("dns_records", records)
