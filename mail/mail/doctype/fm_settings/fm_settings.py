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
		self.validate_smtp_server()
		self.validate_smtp_port()
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

	def validate_smtp_server(self) -> None:
		self.smtp_server = self.smtp_server.lower()

		public_ipv4 = Utils.get_dns_record(self.smtp_server, "A")
		public_ipv6 = Utils.get_dns_record(self.smtp_server, "AAAA")

		self.public_ipv4 = public_ipv4[0].address if public_ipv4 else None
		self.public_ipv6 = public_ipv6[0].address if public_ipv6 else None

		if not public_ipv4 and not public_ipv6:
			frappe.throw(
				_(
					"An A or AAAA record not found for the outgoing server {0}.".format(
						frappe.bold(self.smtp_server)
					)
				)
			)

	def validate_smtp_port(self) -> None:
		if not Utils.is_port_open(self.smtp_server, self.smtp_port):
			frappe.throw(
				_(
					"Port {0} is not open on the outgoing server {1}.".format(
						frappe.bold(self.smtp_port), frappe.bold(self.smtp_server)
					)
				)
			)

	def validate_incoming_servers(self) -> None:
		server_list = []
		priority_list = []

		if self.incoming_servers:
			for incoming_server in self.incoming_servers:
				incoming_server.server = incoming_server.server.lower()

				if incoming_server.server in server_list:
					frappe.throw(
						_(
							"{0} Row #{1}: Duplicate incoming server {2}.".format(
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

				if incoming_server.server != self.smtp_server:
					if not Utils.get_dns_record(
						incoming_server.server, "A"
					) or not Utils.get_dns_record(incoming_server.server, "AAAA"):
						frappe.throw(
							_(
								"{0} Row #{1}: An A or AAAA record not found for the incoming server {2}.".format(
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
		category = "Server Record"

		# A Record
		if self.public_ipv4:
			records.append(
				{
					"category": category,
					"type": "A",
					"host": self.smtp_server,
					"value": self.public_ipv4,
					"ttl": self.default_ttl,
				}
			)

		# AAAA Record
		if self.public_ipv6:
			records.append(
				{
					"category": category,
					"type": "AAAA",
					"host": self.smtp_server,
					"value": self.public_ipv6,
					"ttl": self.default_ttl,
				}
			)

		# TXT Record
		records.append(
			{
				"category": category,
				"type": "TXT",
				"host": f"{self.spf_host}.{self.primary_domain_name}",
				"value": f"v=spf1 a:{self.smtp_server} ~all",
				"ttl": self.default_ttl,
			}
		)

		self.extend("dns_records", records)
