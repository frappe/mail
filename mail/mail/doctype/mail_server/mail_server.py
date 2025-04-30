# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order

from mail.mail.doctype.dns_record.dns_record import create_or_update_dns_record
from mail.mail.doctype.mail_server_config.mail_server_config import create_mail_server_config
from mail.mail.doctype.mail_settings.mail_settings import (
	validate_mail_settings,
)
from mail.mail_server import MailServerAPI
from mail.utils.dns import get_dns_record

if TYPE_CHECKING:
	from mail.mail.doctype.mail_server_config.mail_server_config import MailServerConfig


class MailServer(Document):
	def autoname(self) -> None:
		self.hostname = self.hostname.lower()
		self.name = self.hostname

	def validate(self) -> None:
		if self.is_new():
			validate_mail_settings()

		self.validate_hostname()
		self.validate_cluster()
		self.validate_base_url()
		self.validate_cluster_node_id()
		self.validate_acme_providers()
		self.validate_tls_certificates()
		self.validate_listeners()

	def after_insert(self) -> None:
		self.generate_config()

	def on_update(self) -> None:
		if self.has_value_changed("enabled"):
			create_or_update_spf_dns_record()
			self.create_or_delete_spf_ehlo_dns_record()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Server."))

		if frappe.db.get_value("Mail Cluster", self.cluster, "outbound"):
			self.db_set("enabled", 0)
			create_or_update_spf_dns_record()
			self.create_or_delete_spf_ehlo_dns_record()

	def validate_hostname(self) -> None:
		"""Validates the server and fetches the IP addresses."""

		if self.is_new() and frappe.db.exists("Mail Server", self.hostname):
			frappe.throw(_("Mail Server {0} already exists.").format(frappe.bold(self.hostname)))

		if ipv4_addresses := [r.address for r in get_dns_record(self.hostname, "A") or []]:
			if len(ipv4_addresses) > 1:
				frappe.throw(
					_("Multiple IPv4 addresses found for Mail Server {0}. Found: {1}.").format(
						frappe.bold(self.hostname), ", ".join(ipv4_addresses)
					)
				)

			self.public_ipv4 = ipv4_addresses[0]

		if ipv6_addresses := [r.address for r in get_dns_record(self.hostname, "AAAA") or []]:
			if len(ipv6_addresses) > 1:
				frappe.throw(
					_("Multiple IPv6 addresses found for Mail Server {0}. Found: {1}.").format(
						frappe.bold(self.hostname), ", ".join(ipv6_addresses)
					)
				)

			self.public_ipv6 = ipv6_addresses[0]

	def validate_cluster(self) -> None:
		"""Validates the cluster."""

		if not frappe.db.get_value("Mail Cluster", self.cluster, "enabled"):
			frappe.throw(_("Mail Cluster {0} is disabled.").format(frappe.bold(self.cluster)))

	def validate_base_url(self) -> None:
		"""Validates the base URL of the server."""

		if not self.base_url:
			self.base_url = f"https://{self.hostname}/"

	def validate_cluster_node_id(self) -> None:
		"""Validates the cluster node ID."""

		if frappe.db.exists(
			"Mail Server",
			{
				"cluster": self.cluster,
				"cluster_node_id": self.cluster_node_id,
				"name": ["!=", self.name],
			},
		):
			frappe.throw(
				_("Node ID {0} already assigned to another Mail Server.").format(
					frappe.bold(self.cluster_node_id)
				)
			)

	def validate_acme_providers(self) -> None:
		"""Validates the ACME Providers."""

		default_count = 0
		directory_ids = []
		for acme in self.acme_providers:
			if acme.default:
				default_count += 1

			if acme.directory_id in directory_ids:
				frappe.throw(
					_("Row #{0}: Directory ID {1} is duplicated.").format(
						acme.idx, frappe.bold(acme.directory_id)
					)
				)
			directory_ids.append(acme.directory_id)

		if default_count > 1:
			frappe.throw(_("Only one ACME Provider can be default."))

	def validate_tls_certificates(self) -> None:
		"""Validates the TLS Certificates."""

		default_count = 0
		certificate_ids = []
		for tls in self.tls_certificates:
			if tls.default:
				default_count += 1

			if tls.certificate_id in certificate_ids:
				frappe.throw(
					_("Row #{0}: Certificate ID {1} is duplicated.").format(
						tls.idx, frappe.bold(tls.certificate_id)
					)
				)
			certificate_ids.append(tls.certificate_id)

			if not tls.cert and not tls.cert_path:
				frappe.throw(_("Row #{0}: Certificate or Certificate Path is required.").format(tls.idx))
			if not tls.private_key and not tls.private_key_path:
				frappe.throw(_("Row #{0}: Private Key or Private Key Path is required.").format(tls.idx))

		if default_count > 1:
			frappe.throw(_("Only one TLS Certificate can be default."))

	def validate_listeners(self) -> None:
		"""Validates the listeners."""

		listener_ids = []
		for listener in self.listeners:
			if listener.listener_id in listener_ids:
				frappe.throw(
					_("Row #{0}: Listener ID {1} is duplicated.").format(
						listener.idx, frappe.bold(listener.listener_id)
					)
				)

			listener_ids.append(listener.listener_id)

	@frappe.whitelist()
	def generate_config(self) -> None:
		"""Generates the Mail Server Config."""

		frappe.only_for("System Manager")
		self._generate_config()
		frappe.msgprint(_("Mail Server Config created."), indicator="green", alert=True)

	def _generate_config(self) -> "MailServerConfig":
		"""Generates the Mail Server Config."""

		return create_mail_server_config(self.name)

	def create_or_delete_spf_ehlo_dns_record(self) -> None:
		"""Creates or deletes the SPF EHLO DNS Record."""

		mail_settings = frappe.get_cached_doc("Mail Settings")
		if not self.hostname.endswith(f".{mail_settings.root_domain_name}"):
			return

		host = self.hostname[: -len(mail_settings.root_domain_name) - 1]
		if self.enabled:
			create_or_update_dns_record(
				host=host,
				type="TXT",
				value=f"v=spf1 include:{mail_settings.spf_host}.{mail_settings.root_domain_name} ~all",
				ttl=mail_settings.default_ttl,
				category="Server Record",
			)
		else:
			if spf_ehlo_dns_record := frappe.db.exists("DNS Record", {"host": host, "type": "TXT"}):
				frappe.delete_doc("DNS Record", spf_ehlo_dns_record, ignore_permissions=True)

	@frappe.whitelist()
	def reload_config(self) -> None:
		"""Reloads the Mail Server Config."""

		frappe.only_for("System Manager")

		if not self.enabled:
			frappe.throw(_("Mail Server {0} is disabled.").format(frappe.bold(self.name)))

		cluster = frappe.get_cached_doc("Mail Cluster", self.cluster)
		api_key = cluster.get_password("api_key") if cluster.api_key else None
		server_api = MailServerAPI(
			self.base_url,
			api_key=api_key,
			username=cluster.fallback_admin_user,
			password=cluster.get_password("fallback_admin_password"),
		)
		response = server_api.request(method="GET", endpoint="/api/reload")
		if response.status_code != 200:
			frappe.throw(title=_("Request failed for {0}").format(server_api.base_url), msg=response.text)


@frappe.whitelist()
def reload_config(servers: str | list[str]) -> None:
	"""Reloads the Mail Server Config."""

	frappe.only_for("System Manager")

	if isinstance(servers, str):
		servers = json.loads(servers)

	reloaded_servers = []
	for server in servers:
		server = frappe.get_cached_doc("Mail Server", server)
		if server.enabled:
			server.reload_config()
			reloaded_servers.append(server.name)
		else:
			frappe.msgprint(_("Mail Server {0} is disabled.").format(frappe.bold(server.name)), alert=True)

	if reloaded_servers:
		frappe.msgprint(_("Servers Configuration reloaded."), alert=True)


def create_or_update_spf_dns_record(spf_host: str | None = None) -> None:
	"""Refreshes the SPF DNS Record."""

	mail_settings = frappe.get_single("Mail Settings")
	spf_host = spf_host or mail_settings.spf_host

	SERVER = frappe.qb.DocType("Mail Server")
	CLUSTER = frappe.qb.DocType("Mail Cluster")
	outbound_servers = (
		frappe.qb.from_(CLUSTER)
		.join(SERVER)
		.on(CLUSTER.name == SERVER.cluster)
		.select(SERVER.name)
		.where((CLUSTER.enabled == 1) & (CLUSTER.outbound == 1) & (SERVER.enabled == 1))
		.orderby(SERVER.name, order=Order.asc)
	).run(pluck="name")

	if outbound_servers:
		outbound_servers = [f"a:{outbound_server}" for outbound_server in outbound_servers]
		create_or_update_dns_record(
			host=spf_host,
			type="TXT",
			value=f"v=spf1 {' '.join(outbound_servers)} ~all",
			ttl=mail_settings.default_ttl,
			category="Server Record",
		)
	else:
		if spf_dns_record := frappe.db.exists("DNS Record", {"host": spf_host, "type": "TXT"}):
			frappe.delete_doc("DNS Record", spf_dns_record, ignore_permissions=True)


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mail Server", ["cluster", "cluster_node_id"], constraint_name="unique_cluster_node_id"
	)
