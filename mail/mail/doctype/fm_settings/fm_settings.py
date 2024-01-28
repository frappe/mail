# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from mail.utils import Utils
from frappe.utils import cint
from frappe.model.document import Document


class FMSettings(Document):
	def validate(self) -> None:
		self.validate_primary_domain_name()
		self.validate_spf_host()
		self.validate_default_dkim_selector()
		self.validate_default_dkim_bits()
		self.generate_dns_records()

	def validate_primary_domain_name(self) -> None:
		self.primary_domain_name = self.primary_domain_name.lower()

	def validate_spf_host(self) -> None:
		self.spf_host = self.spf_host.lower()

		if not Utils.is_valid_host(self.spf_host):
			msg = _(
				"SPF Host {0} is invalid. It can be alphanumeric but should not contain spaces or special characters, excluding underscores.".format(
					frappe.bold(self.spf_host)
				)
			)
			frappe.throw(msg)

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

	def generate_dns_records(self, save: bool = False) -> None:
		self.dns_records.clear()

		servers = frappe.db.get_all(
			"FM Server",
			filters={"enabled": 1, "outgoing": 1},
			fields=["name", "outgoing", "ipv4", "ipv6"],
			order_by="creation asc",
		)

		if servers:
			records = []
			outgoing_servers = []
			category = "Server Record"

			for server in servers:
				if server.outgoing:
					# A Record
					if server.ipv4:
						records.append(
							{
								"category": category,
								"type": "A",
								"host": server.name,
								"value": server.ipv4,
								"ttl": self.default_ttl,
							}
						)

					# AAAA Record
					if server.ipv6:
						records.append(
							{
								"category": category,
								"type": "AAAA",
								"host": server.name,
								"value": server.ipv6,
								"ttl": self.default_ttl,
							}
						)

					outgoing_servers.append(f"a:{server.name}")

			# TXT Record
			if outgoing_servers:
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

		if save:
			self.save()
