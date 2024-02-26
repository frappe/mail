# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from mail.utils import get_dns_record
from frappe.model.document import Document


class MailServer(Document):
	def autoname(self) -> None:
		self.server = self.server.lower()
		self.name = self.server

	def before_validate(self) -> None:
		if self.is_new():
			validate_mail_settings()

	def validate(self) -> None:
		self.validate_server()
		self.validate_enabled()
		self.validate_incoming()
		self.validate_outgoing()
		self.validate_host()

	def on_update(self) -> None:
		self.update_server_dns_records()

	def on_trash(self) -> None:
		self.db_set("enabled", 0)
		self.update_server_dns_records()

	def validate_server(self) -> None:
		if self.is_new() and frappe.db.exists("Mail Server", self.server):
			frappe.throw(
				_(
					"Mail Server {0} already exists.".format(
						frappe.bold(self.server),
					)
				)
			)

		if frappe.conf.developer_mode or frappe.session.user == "Administrator":
			return

		ipv4 = get_dns_record(self.server, "A")
		ipv6 = get_dns_record(self.server, "AAAA")

		self.ipv4 = ipv4[0].address if ipv4 else None
		self.ipv6 = ipv6[0].address if ipv6 else None

		if not self.ipv4 and not self.ipv6:
			frappe.throw(
				_(
					"An A or AAAA record not found for the server {0}.".format(
						frappe.bold(self.server),
					)
				)
			)

	def validate_enabled(self) -> None:
		if self.enabled and not self.incoming and not self.outgoing:
			self.enabled = 0

		if not self.is_new() and not self.enabled:
			self.remove_linked_domains()

	def validate_incoming(self) -> None:
		if self.incoming:
			if not self.priority:
				frappe.throw(_("Priority is required for incoming servers."))

	def validate_outgoing(self) -> None:
		if not self.outgoing and not self.is_new():
			self.remove_linked_domains()

	def validate_host(self) -> None:
		if self.host:
			self.host = self.host.lower()

	def remove_linked_domains(self) -> None:
		DOMAIN = frappe.qb.DocType("Mail Domain")
		frappe.qb.update(DOMAIN).set(DOMAIN.outgoing_server, None).where(
			DOMAIN.outgoing_server == self.server
		).run()

	def update_server_dns_records(self) -> None:
		frappe.get_doc("Mail Settings").generate_dns_records(save=True)


def validate_mail_settings() -> None:
	mail_settings = frappe.get_doc("Mail Settings")
	mandatory_fields = [
		"root_domain_name",
		"spf_host",
		"default_dkim_selector",
		"default_dkim_bits",
		"default_ttl",
	]

	for field in mandatory_fields:
		if not mail_settings.get(field):
			field_label = frappe.get_meta("Mail Settings").get_label(field)
			frappe.throw(
				_("Please set the {0} in the Mail Settings.".format(frappe.bold(field_label)))
			)
