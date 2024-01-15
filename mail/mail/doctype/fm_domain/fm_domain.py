# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from mail.utils import Utils
from frappe.utils import cint
from frappe.model.document import Document
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from mail.mail.doctype.fm_dns_record.fm_dns_record import FMDNSRecord
from mail.mail.doctype.fm_incoming_server.fm_incoming_server import FMIncomingServer


class FMDomain(Document):
	def autoname(self) -> None:
		self.domain_name = self.domain_name.lower()
		self.name = self.domain_name

	def validate(self) -> None:
		self.validate_domain_name()
		self.validate_dkim_selector()
		self.validate_dkim_bits()
		self.validate_is_primary_domain()

		if self.is_new() or (self.dkim_bits != self.get_doc_before_save().get("dkim_bits")):
			self.generate_dns_records()
		elif self.dkim_selector != self.get_doc_before_save().get("dkim_selector"):
			self.refresh_dns_records()
		elif not self.is_active:
			self.is_verified = 0

	def validate_domain_name(self) -> None:
		if not Utils.is_valid_domain(self.domain_name):
			frappe.throw(_("Domain Name {0} is invalid.".format(frappe.bold(self.domain_name))))

	def validate_dkim_selector(self) -> None:
		if self.dkim_selector:
			self.dkim_selector = self.dkim_selector.lower()

			if not Utils.is_valid_host(self.dkim_selector):
				msg = _(
					"DKIM Selector {0} is invalid. It can be alphanumeric but should not contain spaces or special characters, excluding underscores.".format(
						frappe.bold(self.dkim_selector)
					)
				)
				frappe.throw(msg)
		else:
			self.dkim_selector = frappe.db.get_single_value(
				"FM Settings", "default_dkim_selector"
			)

	def validate_dkim_bits(self) -> None:
		if self.dkim_bits:
			if cint(self.dkim_bits) < 1024:
				frappe.throw(_("DKIM Bits must be greater than 1024."))
		else:
			self.dkim_bits = frappe.db.get_single_value("FM Settings", "default_dkim_bits")

	def validate_is_primary_domain(self) -> None:
		self.is_primary_domain = (
			1
			if self.domain_name
			== frappe.db.get_single_value("FM Settings", "primary_domain_name")
			else 0
		)

	@frappe.whitelist()
	def generate_dns_records(self, save: bool = False) -> None:
		self.is_verified = 0
		self.generate_dkim_key()
		self.refresh_dns_records()

		if save:
			self.save()

	def generate_dkim_key(self) -> None:
		private_key = rsa.generate_private_key(
			public_exponent=65537, key_size=cint(self.dkim_bits), backend=default_backend()
		)
		public_key = private_key.public_key()

		private_key_pem = private_key.private_bytes(
			encoding=serialization.Encoding.PEM,
			format=serialization.PrivateFormat.TraditionalOpenSSL,
			encryption_algorithm=serialization.NoEncryption(),
		).decode()
		public_key_pem = public_key.public_bytes(
			encoding=serialization.Encoding.PEM,
			format=serialization.PublicFormat.SubjectPublicKeyInfo,
		).decode()

		self.dkim_private_key = private_key_pem
		self.dkim_public_key = get_filtered_dkim_key(public_key_pem)

	def refresh_dns_records(self) -> None:
		self.is_verified = 0
		self.dns_records.clear()
		fm_settings = frappe.get_single("FM Settings")

		sending_records = self.get_sending_records(
			fm_settings.primary_domain_name, fm_settings.spf_host, fm_settings.default_ttl
		)
		receiving_records = self.get_receiving_records(
			fm_settings.incoming_servers, fm_settings.default_ttl
		)

		self.extend("dns_records", sending_records)
		self.extend("dns_records", receiving_records)

	def get_sending_records(
		self, primary_domain_name: str, spf_host: str, ttl: str
	) -> list[dict]:
		records = []
		type = "TXT"
		category = "Sending Record"

		# SPF Record
		records.append(
			{
				"category": category,
				"type": type,
				"host": self.domain_name,
				"value": f"v=spf1 include:{spf_host}.{primary_domain_name} ~all",
				"ttl": ttl,
			},
		)

		# DKIM Record
		records.append(
			{
				"category": category,
				"type": type,
				"host": f"{self.dkim_selector}._domainkey.{self.domain_name}",
				"value": f"v=DKIM1;k=rsa;p={self.dkim_public_key}",
				"ttl": ttl,
			}
		)

		# DMARC Record
		records.append(
			{
				"category": category,
				"type": type,
				"host": f"_dmarc.{self.domain_name}",
				"value": f"v=DMARC1; p=reject; sp=reject; pct=100; rua=mailto:dmarc@{self.domain_name}; ri=86400; aspf=s; adkim=s; fo=1",
				"ttl": ttl,
			}
		)

		return records

	def get_receiving_records(
		self, incoming_servers: list[FMIncomingServer], ttl
	) -> list[dict]:
		records = []

		for row in incoming_servers:
			records.append(
				{
					"category": "Receiving Record",
					"type": "MX",
					"host": self.domain_name,
					"value": f"{row.server}.",
					"priority": row.priority,
					"ttl": ttl,
				}
			)

		return records

	@frappe.whitelist()
	def verify_dns_records(self, save: bool = False) -> None:
		self.is_verified = 1

		for record in self.dns_records:
			if verify_dns_record(record):
				record.is_verified = 1
				frappe.msgprint(
					_("Row #{0}: Verified {1}:{2} record.").format(
						frappe.bold(record.idx), frappe.bold(record.type), frappe.bold(record.host)
					),
					indicator="green",
					alert=True,
				)
			else:
				record.is_verified = 0
				self.is_verified = 0
				frappe.msgprint(
					_("Row #{0}: Could not verify {1}:{2} record.").format(
						frappe.bold(record.idx), frappe.bold(record.type), frappe.bold(record.host)
					),
					indicator="orange",
					alert=True,
				)

		if save:
			self.save()


def get_filtered_dkim_key(key_pem: str) -> str:
	key_pem = "".join(key_pem.split())
	key_pem = (
		key_pem.replace("-----BEGINPUBLICKEY-----", "")
		.replace("-----ENDPUBLICKEY-----", "")
		.replace("-----BEGINRSAPRIVATEKEY-----", "")
		.replace("----ENDRSAPRIVATEKEY-----", "")
	)

	return key_pem


def verify_dns_record(record: FMDNSRecord, debug: bool = False) -> bool:
	if result := Utils.get_dns_record(record.host, record.type):
		for data in result:
			if data:
				if record.type == "MX":
					data = data.exchange

				data = data.to_text().replace('"', "")

				if record.type == "TXT" and "._domainkey." in record.host:
					data = data.replace(" ", "")

				if data == record.value:
					return True

			if debug:
				frappe.msgprint(f"Expected: {record.value} Got: {data}")

	return False
