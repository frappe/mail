# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint
from typing import Optional, TYPE_CHECKING
from frappe.model.document import Document
from mail.mail.doctype.mailbox.mailbox import create_dmarc_mailbox
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from mail.utils import (
	is_system_manager,
	get_dns_record,
	is_valid_host,
	get_user_domains,
)

if TYPE_CHECKING:
	from mail.mail.doctype.dns_record.dns_record import DNSRecord


class MailDomain(Document):
	def autoname(self) -> None:
		self.domain_name = self.domain_name.lower()
		self.name = self.domain_name

	def validate(self) -> None:
		self.validate_dkim_selector()
		self.validate_dkim_bits()
		self.validate_outgoing_agent()
		self.validate_subdomain()
		self.validate_root_domain()

		if self.is_new() or (self.dkim_bits != self.get_doc_before_save().get("dkim_bits")):
			self.generate_dns_records()
		elif self.dkim_selector != self.get_doc_before_save().get("dkim_selector"):
			self.refresh_dns_records()
		elif not self.enabled:
			self.verified = 0

	def on_update(self) -> None:
		previous = self.get_doc_before_save()

		if not previous:
			create_dmarc_mailbox(self.domain_name)
			self.sync_mail_domain(enabled=self.enabled)
		elif self.enabled != previous.get("enabled"):
			self.sync_mail_domain(enabled=self.enabled)

	def on_trash(self) -> None:
		self.sync_mail_domain(enabled=False)

	def validate_dkim_selector(self) -> None:
		"""Validates the DKIM Selector."""

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
		"""Validates the DKIM Bits."""

		if self.dkim_bits:
			if cint(self.dkim_bits) < 1024:
				frappe.throw(_("DKIM Bits must be greater than 1024."))
		else:
			self.dkim_bits = frappe.db.get_single_value("Mail Settings", "default_dkim_bits")

	def validate_outgoing_agent(self) -> None:
		"""Validates the Outgoing Agent."""

		if self.outgoing_agent:
			enabled, outgoing = frappe.db.get_value(
				"Mail Agent", self.outgoing_agent, ["enabled", "outgoing"]
			)

			if not enabled:
				frappe.throw(
					_("Outgoing Agent {0} is disabled.".format(frappe.bold(self.outgoing_agent)))
				)

			if not outgoing:
				frappe.throw(
					_(
						"Outgoing Agent {0} is not an valid outgoing agent.".format(
							frappe.bold(self.outgoing_agent)
						)
					)
				)

	def validate_subdomain(self) -> None:
		"""Validates if the domain is a subdomain."""

		if len(self.domain_name.split(".")) > 2:
			self.subdomain = 1

	def validate_root_domain(self) -> None:
		"""Validates if the domain is the root domain."""

		self.root_domain = (
			1
			if self.domain_name
			== frappe.db.get_single_value("Mail Settings", "root_domain_name")
			else 0
		)

	@frappe.whitelist()
	def generate_dns_records(self, save: bool = False) -> None:
		"""Generates the DNS Records."""

		self.verified = 0
		self.generate_dkim_key()
		self.refresh_dns_records()

		if save:
			self.save()

	def generate_dkim_key(self) -> None:
		"""Generates the DKIM Key."""

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
		"""Refreshes the DNS Records."""

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
		"""Returns the Sending Records."""

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
		dmarc_value = (
			f"v=DMARC1; p=none; rua=mailto:dmarc@{self.domain_name}; ruf=mailto:dmarc@{self.domain_name};"
			if self.root_domain
			else f"v=DMARC1; p=reject; rua=mailto:dmarc@{self.domain_name}; ruf=mailto:dmarc@{self.domain_name};"
		)
		records.append(
			{
				"category": category,
				"type": type,
				"host": f"_dmarc.{self.domain_name}",
				"value": dmarc_value,
				"ttl": ttl,
			}
		)

		return records

	def get_receiving_records(self, ttl: str) -> list[dict]:
		"""Returns the Receiving Records."""

		records = []
		incoming_agents = frappe.db.get_all(
			"Mail Agent",
			filters={"enabled": 1, "incoming": 1},
			fields=["name", "priority"],
			order_by="priority",
		)

		if incoming_agents:
			for agent in incoming_agents:
				records.append(
					{
						"category": "Receiving Record",
						"type": "MX",
						"host": self.domain_name,
						"value": f"{agent.name.split(':')[0]}.",
						"priority": agent.priority,
						"ttl": ttl,
					}
				)

		return records

	@frappe.whitelist()
	def verify_dns_records(self, save: bool = False) -> None:
		"""Verifies the DNS Records."""

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

	def sync_mail_domain(self, enabled: bool | int) -> None:
		"""Updates the domain in the agents."""

		domains = [{"domain": self.domain_name, "enabled": 1 if enabled else 0}]
		sync_mail_domains(domains)


def get_filtered_dkim_key(key_pem: str) -> str:
	"""Returns the filtered DKIM Key."""

	key_pem = "".join(key_pem.split())
	key_pem = (
		key_pem.replace("-----BEGINPUBLICKEY-----", "")
		.replace("-----ENDPUBLICKEY-----", "")
		.replace("-----BEGINRSAPRIVATEKEY-----", "")
		.replace("----ENDRSAPRIVATEKEY-----", "")
	)

	return key_pem


def verify_dns_record(record: "DNSRecord", debug: bool = False) -> bool:
	"""Verifies the DNS Record."""

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
def sync_mail_domains(
	mail_domains: Optional[list[dict]] = None, agents: Optional[str | list] = None
) -> None:
	"""Updates the domains in the agents."""

	if not mail_domains:
		mail_domains = frappe.db.get_all(
			"Mail Domain", filters={"enabled": 1}, fields=["name AS domain", "enabled"]
		)

	if mail_domains:
		if not agents:
			agents = frappe.db.get_all(
				"Mail Agent", filters={"enabled": 1, "incoming": 1}, pluck="name"
			)
		elif isinstance(agents, str):
			agents = [agents]

		for agent in agents:
			create_agent_job(
				agent, "Sync Mail Domains", request_data={"mail_domains": mail_domains}
			)


def has_permission(doc: "Document", ptype: str, user: str) -> bool:
	if doc.doctype != "Mail Domain":
		return False

	return is_system_manager(user) or (user == doc.owner)


def get_permission_query_condition(user: Optional[str]) -> str:
	if not user:
		user = frappe.session.user

	if is_system_manager(user):
		return ""

	domains = ", ".join(repr(d) for d in get_user_domains(user))

	return f"(`tabMail Domain`.`owner` = {frappe.db.escape(user)}) OR (`tabMail Domain`.`domain_name` IN ({domains}))"
