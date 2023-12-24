# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import rsa
import frappe
from frappe import _
from frappe.model.document import Document
from mail.mail.doctype.fm_smtp_server.fm_smtp_server import FMSMTPServer


class FMDomain(Document):
	def validate(self) -> None:
		self.validate_dkim_selector()
		self.validate_dkim_bits()

		if self.is_new() or (self.dkim_bits != self.get_doc_before_save().get("dkim_bits")):
			self.generate_dkim_key()
			self.generate_dns_records()
		elif self.dkim_selector != self.get_doc_before_save().get("dkim_selector"):
			self.generate_dns_records()

	def validate_dkim_selector(self) -> None:
		if not self.dkim_selector:
			self.dkim_selector = frappe.db.get_single_value(
				"FM Settings", "default_dkim_selector"
			)

	def validate_dkim_bits(self):
		if self.dkim_bits:
			if self.dkim_bits < 1024:
				frappe.throw(_("DKIM Bits must be greater than 1024."))
		else:
			self.dkim_bits = frappe.db.get_single_value("FM Settings", "default_dkim_bits")

	def generate_dns_records(self) -> None:
		self.dns_records.clear()
		fm_settings = frappe.get_single("FM Settings")

		sending_records = self.get_sending_records(
			fm_settings.spf_host, fm_settings.default_ttl
		)
		receiving_records = self.get_receiving_records(
			fm_settings.smtp_servers, fm_settings.default_ttl
		)

		self.extend("dns_records", sending_records)
		self.extend("dns_records", receiving_records)

	def generate_dkim_key(self):
		public_key, private_key = rsa.newkeys(self.dkim_bits)
		private_key_pem = private_key.save_pkcs1().decode("utf-8")
		public_key_pem = public_key.save_pkcs1().decode("utf-8")

		self.dkim_private_key = get_filtered_dkim_key(private_key_pem)
		self.dkim_public_key = get_filtered_dkim_key(public_key_pem)

	def get_sending_records(self, spf_host: str, ttl: str) -> list[dict]:
		records = []
		type = "TXT"
		category = "Sending Record"

		# SPF
		records.append(
			{
				"category": category,
				"type": type,
				"host": self.domain_name,
				"value": f"v=spf1 include:{spf_host} ~all",
				"ttl": ttl,
			},
		)

		# DKIM
		records.append(
			{
				"category": category,
				"type": type,
				"host": f"{self.dkim_selector}._domainkey.{self.domain_name}",
				"value": f"v=DKIM1; k=rsa; p={self.dkim_public_key}",
				"ttl": ttl,
			}
		)

		# DMARC
		records.append(
			{
				"category": category,
				"type": type,
				"host": f"_dmarc.{self.domain_name}",
				"value": "v=DMARC1; p=none;",
				"ttl": ttl,
			}
		)

		return records

	def get_receiving_records(self, smtp_servers: list[FMSMTPServer], ttl) -> list[dict]:
		records = []

		for row in smtp_servers:
			records.append(
				{
					"category": "Receiving Record",
					"type": "MX",
					"host": self.domain_name,
					"value": row.smtp_server,
					"priority": row.priority,
					"ttl": ttl,
				}
			)

		return records


def get_filtered_dkim_key(public_key_pem) -> str:
	public_key_pem = "".join(public_key_pem.split())
	public_key_pem = public_key_pem.replace("-----BEGINRSAPUBLICKEY-----", "").replace("-----ENDRSAPUBLICKEY-----", "").replace("-----BEGINRSAPRIVATEKEY-----", "").replace("----ENDRSAPRIVATEKEY-----", "")

	return public_key_pem
