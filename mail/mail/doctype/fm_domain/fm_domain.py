# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import rsa
import frappe
import dns.resolver
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document
from mail.mail.doctype.fm_dns_record.fm_dns_record import FMDNSRecord
from mail.mail.doctype.fm_smtp_server.fm_smtp_server import FMSMTPServer


class FMDomain(Document):
	def validate(self) -> None:
		self.validate_dkim_selector()
		self.validate_dkim_bits()

		if self.is_new() or (self.dkim_bits != self.get_doc_before_save().get("dkim_bits")):
			self.generate_dns_records()
		elif self.dkim_selector != self.get_doc_before_save().get("dkim_selector"):
			self.refresh_dns_records()

	def validate_dkim_selector(self) -> None:
		if not self.dkim_selector:
			self.dkim_selector = frappe.db.get_single_value(
				"FM Settings", "default_dkim_selector"
			)

	def validate_dkim_bits(self) -> None:
		if self.dkim_bits:
			if cint(self.dkim_bits) < 1024:
				frappe.throw(_("DKIM Bits must be greater than 1024."))
		else:
			self.dkim_bits = frappe.db.get_single_value("FM Settings", "default_dkim_bits")

	@frappe.whitelist()
	def generate_dns_records(self, save=False) -> None:
		self.generate_dkim_key()
		self.refresh_dns_records()

		if save:
			self.save()

	def generate_dkim_key(self) -> None:
		public_key, private_key = rsa.newkeys(cint(self.dkim_bits))
		private_key_pem = private_key.save_pkcs1().decode("utf-8")
		public_key_pem = public_key.save_pkcs1().decode("utf-8")

		self.dkim_private_key = get_filtered_dkim_key(private_key_pem)
		self.dkim_public_key = get_filtered_dkim_key(public_key_pem)

	def refresh_dns_records(self) -> None:
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
					"value": f"{row.smtp_server}.",
					"priority": row.priority,
					"ttl": ttl,
				}
			)

		return records

	@frappe.whitelist()
	def verify_dns_records(self, save=False) -> None:
		for record in self.dns_records:
			if verify_dns_record(record):
				record.verified = 1
				frappe.msgprint(
					_("Row #{0}: Verified {1}:{2} record.").format(
						frappe.bold(record.idx), frappe.bold(record.type), frappe.bold(record.host)
					),
					indicator="green",
					alert=True,
				)
			else:
				record.verified = 0
				frappe.msgprint(
					_("Row #{0}: Could not verify {1}:{2} record.").format(
						frappe.bold(record.idx), frappe.bold(record.type), frappe.bold(record.host)
					),
					indicator="orange",
					alert=True,
				)

		if save:
			self.save()


def get_filtered_dkim_key(public_key_pem) -> str:
	public_key_pem = "".join(public_key_pem.split())
	public_key_pem = (
		public_key_pem.replace("-----BEGINRSAPUBLICKEY-----", "")
		.replace("-----ENDRSAPUBLICKEY-----", "")
		.replace("-----BEGINRSAPRIVATEKEY-----", "")
		.replace("----ENDRSAPRIVATEKEY-----", "")
	)

	return public_key_pem


def verify_dns_record(record: FMDNSRecord, debug=False) -> bool:
	if result := get_dns_record(record.host, record.type):
		for data in result:
			if data:
				if record.type == "MX":
					data = data.exchange

				data = data.to_text().replace('"', "")

				if data == record.value:
					return True

			if debug:
				frappe.msgprint(f"Expected: {record.value} Got: {data}")

	return False


def get_dns_record(
	host: str, type: str, raise_exception=False
) -> dns.resolver.Answer | None:
	err_msg = None

	try:
		resolver = dns.resolver.Resolver(configure=False)
		resolver.nameservers = frappe.db.get_single_value(
			"FM Settings", "dns_nameservers"
		).split()

		return resolver.resolve(host, type)
	except dns.resolver.NXDOMAIN:
		err_msg = "Host does not exist."
	except dns.resolver.NoAnswer:
		err_msg = "No record found."
	except dns.exception.DNSException as e:
		err_msg = e

	if raise_exception and err_msg:
		frappe.throw(err_msg)
