# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document


class FMSettings(Document):
	def validate(self):
		self.validate_default_dkim_bits()
		self.generate_dns_records()

	def validate_default_dkim_bits(self):
		if cint(self.default_dkim_bits) < 1024:
			frappe.throw(_("DKIM Bits must be greater than 1024."))

	def generate_dns_records(self):
		self.dns_records.clear()

		records = []
		category = "Server Record"

		# A Record
		if self.public_ip:
			records.append(
				{
					"category": category,
					"type": "A",
					"host": self.smtp_server,
					"value": self.public_ip,
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
