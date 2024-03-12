# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint
from typing import TYPE_CHECKING, Optional
from frappe.model.document import Document
from mail.utils import get_dns_record, is_valid_host
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job

if TYPE_CHECKING:
	from mail.mail.doctype.dns_record.dns_record import DNSRecord


class MailDomain(Document):
	def autoname(self) -> None:
		self.domain_name = self.domain_name.lower()
		self.name = self.domain_name

	def validate(self) -> None:
		self.validate_dkim_selector()
		self.validate_dkim_bits()
		self.validate_outgoing_server()
		self.validate_root_domain()

		if self.is_new() or (self.dkim_bits != self.get_doc_before_save().get("dkim_bits")):
			self.generate_dns_records()
		elif self.dkim_selector != self.get_doc_before_save().get("dkim_selector"):
			self.refresh_dns_records()
		elif not self.enabled:
			self.verified = 0

	def on_update(self) -> None:
		previous = self.get_doc_before_save()

		if not previous or self.enabled != previous.get("enabled"):
			virtual_domains = [{"domain": self.domain_name, "enabled": self.enabled}]
			update_virtual_domains(virtual_domains)

	def on_trash(self) -> None:
		virtual_domains = [{"domain": self.domain_name, "enabled": 0}]
		update_virtual_domains(virtual_domains)

	def validate_dkim_selector(self) -> None:
		if self.dkim_selector:
			self.dkim_selector = self.dkim_selector.lower()

			if not is_valid_host(self.dkim_selector):
				msg = _(
					"DKIM Selector {0} is invalid. It can be alphanumeric but should not contain spaces or special characters, excluding underscores.".format(
						frappe.bold(self.dkim_selector)
					)
				)
				frappe.throw(msg)
		else:
			self.dkim_selector = frappe.db.get_single_value(
				"Mail Settings", "default_dkim_selector"
			)

	def validate_dkim_bits(self) -> None:
		if self.dkim_bits:
			if cint(self.dkim_bits) < 1024:
				frappe.throw(_("DKIM Bits must be greater than 1024."))
		else:
			self.dkim_bits = frappe.db.get_single_value("Mail Settings", "default_dkim_bits")

	def validate_outgoing_server(self) -> None:
		if self.outgoing_server:
			enabled, outgoing = frappe.db.get_value(
				"Mail Server", self.outgoing_server, ["enabled", "outgoing"]
			)

			if not enabled:
				frappe.throw(
					_("Outgoing Server {0} is disabled.".format(frappe.bold(self.outgoing_server)))
				)

			if not outgoing:
				frappe.throw(
					_(
						"Outgoing Server {0} is not an valid outgoing server.".format(
							frappe.bold(self.outgoing_server)
						)
					)
				)

	def validate_root_domain(self) -> None:
		self.root_domain = (
			1
			if self.domain_name
			== frappe.db.get_single_value("Mail Settings", "root_domain_name")
			else 0
		)

	@frappe.whitelist()
	def generate_dns_records(self, save: bool = False) -> None:
		self.verified = 0
		self.generate_dkim_key()
		self.refresh_dns_records()

		if save:
			self.save()

	def generate_dkim_key(self) -> None:
		from cryptography.hazmat.backends import default_backend
		from cryptography.hazmat.primitives import serialization
		from cryptography.hazmat.primitives.asymmetric import rsa

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
		self.verified = 0
		self.dns_records.clear()
		mail_settings = frappe.get_single("Mail Settings")

		sending_records = self.get_sending_records(
			mail_settings.root_domain_name, mail_settings.spf_host, mail_settings.default_ttl
		)
		receiving_records = self.get_receiving_records(mail_settings.default_ttl)

		self.extend("dns_records", sending_records)
		self.extend("dns_records", receiving_records)

	def get_sending_records(
		self, root_domain_name: str, spf_host: str, ttl: str
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
				"value": f"v=spf1 include:{spf_host}.{root_domain_name} ~all",
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

	def get_receiving_records(self, ttl: str) -> list[dict]:
		records = []
		incoming_servers = frappe.db.get_all(
			"Mail Server",
			filters={"enabled": 1, "incoming": 1},
			fields=["name", "priority"],
			order_by="priority",
		)

		if incoming_servers:
			for server in incoming_servers:
				records.append(
					{
						"category": "Receiving Record",
						"type": "MX",
						"host": self.domain_name,
						"value": f"{server.name.split(':')[0]}.",
						"priority": server.priority,
						"ttl": ttl,
					}
				)

		return records

	@frappe.whitelist()
	def verify_dns_records(self, save: bool = False) -> None:
		self.verified = 1

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
				self.verified = 0
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


def verify_dns_record(record: "DNSRecord", debug: bool = False) -> bool:
	if result := get_dns_record(record.host, record.type):
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


@frappe.whitelist()
def update_virtual_domains(
	virtual_domains: Optional[list[dict]] = None, servers: Optional[str | list] = None
) -> None:
	if not virtual_domains:
		virtual_domains = frappe.db.get_all(
			"Mail Domain", {"enabled": 1}, ["name AS domain", "enabled"]
		)

	if virtual_domains:
		if not servers:
			servers = frappe.db.get_all(
				"Mail Server", {"enabled": 1, "incoming": 1}, pluck="name"
			)
		elif isinstance(servers, str):
			servers = [servers]

		for server in servers:
			create_agent_job(
				server, "Update Virtual Domains", request_data={"virtual_domains": virtual_domains}
			)
