# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import io
import json
import os
import socket
from typing import TYPE_CHECKING

import frappe
import paramiko
from frappe import _
from frappe.model.document import Document

from mail.mail.doctype.mail_settings.mail_settings import (
	validate_mail_settings,
)
from mail.server.doctype.dns_record.dns_record import create_or_update_dns_record
from mail.server.doctype.mail_backend_request.mail_backend_request import create_mail_backend_request
from mail.server.doctype.mail_cluster.mail_cluster import create_or_update_spf_dns_record_for_cluster
from mail.server.doctype.server_config.server_config import create_server_config
from mail.utils import get_spf_host_for_cluster
from mail.utils.cache import get_root_domain_name
from mail.utils.dns import get_dns_record

if TYPE_CHECKING:
	from mail.server.doctype.server_config.server_config import ServerConfig


class MailServer(Document):
	@property
	def ssh_public_key(self) -> str | None:
		"""Returns the SSH public key of the cluster."""

		return frappe.db.get_value("Mail Cluster", self.cluster, "ssh_public_key")

	def autoname(self) -> None:
		self.hostname = self.hostname.lower()
		self.name = self.hostname

	def validate(self) -> None:
		if self.is_new():
			validate_mail_settings()

		self.validate_hostname()
		self.validate_cluster()
		self.validate_base_url()
		self.validate_outbound_only()
		self.validate_priority()
		self.validate_cluster_node_id()
		self.validate_acme_providers()
		self.validate_tls_certificates()
		self.validate_listeners()

	def after_insert(self) -> None:
		self.generate_config()

	def on_update(self) -> None:
		if self.has_value_changed("enabled"):
			create_or_update_spf_dns_record_for_cluster(self.cluster)
			self.create_or_delete_spf_ehlo_dns_record()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Server."))

		self.db_set("enabled", 0)
		create_or_update_spf_dns_record_for_cluster(self.cluster)
		self.create_or_delete_spf_ehlo_dns_record()

	def validate_hostname(self) -> None:
		"""Validates the server and fetches the IP addresses."""

		if self.is_new() and frappe.db.exists("Mail Server", self.hostname):
			frappe.throw(_("Mail Server {0} already exists.").format(frappe.bold(self.hostname)))

		self.ipv4_addresses = "\n".join([r.address for r in get_dns_record(self.hostname, "A") or []])
		self.ipv6_addresses = "\n".join([r.address for r in get_dns_record(self.hostname, "AAAA") or []])

	def validate_cluster(self) -> None:
		"""Validates the cluster."""

		if not frappe.db.get_value("Mail Cluster", self.cluster, "enabled"):
			frappe.throw(_("Mail Cluster {0} is disabled.").format(frappe.bold(self.cluster)))

	def validate_base_url(self) -> None:
		"""Validates the base URL of the server."""

		if not self.base_url:
			self.base_url = f"https://{self.hostname}/"

	def validate_outbound_only(self) -> None:
		"""Validates the outbound only setting."""

		if self.outbound_only:
			self.include_in_mx_records = 0

	def validate_priority(self) -> None:
		"""Validates the priority of the server."""

		if not self.include_in_mx_records:
			self.priority = 0
		else:
			if not self.priority or self.priority < 1:
				frappe.throw(_("Priority must be greater than 0."))

			if frappe.db.exists(
				"Mail Server",
				{"enabled": 1, "cluster": self.cluster, "priority": self.priority, "name": ["!=", self.name]},
			):
				frappe.throw(
					_("Priority {0} is already assigned to another Mail Server.").format(
						frappe.bold(self.priority)
					)
				)

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
		"""Generates the Server Config."""

		frappe.only_for("System Manager")
		self._generate_config()
		frappe.msgprint(_("Server Config created."), indicator="green", alert=True)

	def _generate_config(self) -> "ServerConfig":
		"""Generates the Server Config."""

		return create_server_config(self.name)

	def create_or_delete_spf_ehlo_dns_record(self) -> None:
		"""Creates or deletes the SPF EHLO DNS Record."""

		root_domain_name = get_root_domain_name()

		if not self.hostname.endswith(f".{root_domain_name}"):
			return

		host = self.hostname[: -len(root_domain_name) - 1]
		spf_host = get_spf_host_for_cluster(self.cluster)
		default_ttl = frappe.db.get_single_value("Mail Settings", "default_ttl")
		if self.enabled:
			create_or_update_dns_record(
				host=host,
				type="TXT",
				value=f"v=spf1 include:{spf_host}.{root_domain_name} ~all",
				ttl=default_ttl,
				category="Server Record",
			)
		else:
			if spf_ehlo_dns_record := frappe.db.exists("DNS Record", {"host": host, "type": "TXT"}):
				frappe.delete_doc("DNS Record", spf_ehlo_dns_record, ignore_permissions=True)

	@frappe.whitelist()
	def reload_config(self) -> None:
		"""Reloads the Server configuration."""

		frappe.only_for("System Manager")

		if not self.enabled:
			frappe.throw(_("Mail Server {0} is disabled.").format(frappe.bold(self.name)))

		create_mail_backend_request(
			self.doctype, self.name, method="GET", endpoint="/api/reload", do_not_enqueue=True
		)

	@frappe.whitelist()
	def verify_ssh_connection(self) -> None:
		"""Verifies the SSH connection to the server."""

		frappe.only_for("System Manager")
		success, message = self._verify_ssh_connection()

		if success:
			self._db_set(ssh_verified=1, notify=True)
			frappe.msgprint(message, indicator="green", alert=True)
		else:
			self._db_set(ssh_verified=0, notify=True)
			frappe.msgprint(message, indicator="red", alert=False)

	def _verify_ssh_connection(self) -> tuple[bool, str]:
		"""Verifies the SSH connection to the server."""

		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.settimeout(5)
		try:
			sock.connect((self.hostname, self.ssh_port))
		except Exception as e:
			return False, _("Could not connect to {0}:{1}. Error: {2}").format(
				self.hostname, self.ssh_port, str(e)
			)
		finally:
			sock.close()

		cluster = frappe.get_doc("Mail Cluster", self.cluster)
		try:
			client = paramiko.SSHClient()
			client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			key = paramiko.RSAKey.from_private_key(io.StringIO(cluster.get_password("ssh_private_key")))
			client.connect(
				hostname=self.hostname, port=self.ssh_port, username=self.ssh_user, pkey=key, timeout=10
			)
			client.close()
			return True, _("SSH connection successful.")
		except Exception as e:
			return False, _("SSH connection failed. Error: {0}").format(str(e))

	@frappe.whitelist()
	def install_ansible(self) -> None:
		"""Installs Ansible on the Mail Server."""

		frappe.only_for("System Manager")

		if not self.ssh_verified:
			frappe.throw(_("Please verify the SSH connection before installing Ansible."))

		self._install_ansible()
		frappe.msgprint(_("Install of Ansible initiated."), indicator="green", alert=True)

	def _install_ansible(self) -> None:
		"""Installs Ansible on the Mail Server."""

		script_path = os.path.join(frappe.get_app_path("mail", "utils", "ansible"), "install_ansible.sh")
		with open(script_path) as f:
			script_content = f.read()

		job = frappe.new_doc("Mail Server Job")
		job.status = "Pending"
		job.server = self.name
		job.job = "Install Ansible"
		job.append("commands", {"command": script_content})
		job.insert(ignore_permissions=True)

	@frappe.whitelist()
	def install_docker(self) -> None:
		"""Installs Docker on the Mail Server."""

		frappe.only_for("System Manager")

		if not self.ssh_verified:
			frappe.throw(_("Please verify the SSH connection before installing Docker."))

		self._install_docker()
		frappe.msgprint(_("Install of Docker initiated."), indicator="green", alert=True)

	def _install_docker(self) -> None:
		"""Installs Docker on the Mail Server."""

		play = frappe.new_doc("Server Ansible Play")
		play.status = "Pending"
		play.server = self.name
		play.play = "Install Docker"
		play.playbook = "install-docker.yml"
		play.insert(ignore_permissions=True)

	@frappe.whitelist()
	def install_stalwart(self) -> None:
		"""Installs Stalwart on the Mail Server."""

		frappe.only_for("System Manager")

		if not self.ssh_verified:
			frappe.throw(_("Please verify the SSH connection before installing Stalwart."))

		self._install_stalwart()
		frappe.msgprint(_("Install of Stalwart initiated."), indicator="green", alert=True)

	def _install_stalwart(self, config: str | None = None) -> None:
		"""Installs Stalwart on the Mail Server."""

		config = config or frappe.db.get_value("Server Config", {"server": self.name})
		if not config:
			frappe.throw(_("Please generate the Server Config before installing Stalwart."))

		install_redis = 0
		cluster = frappe.get_doc("Mail Cluster", self.cluster)
		for store in cluster.stores:
			if store.type == "Redis/Memcached" and "redis://redis:6379" in store.urls:
				install_redis = 1
				break

		deployment = frappe.new_doc("Mail Server Deployment")
		deployment.status = "Pending"
		deployment.server = self.name
		deployment.config = config
		deployment.install_redis = install_redis
		deployment.insert(ignore_permissions=True)

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


@frappe.whitelist()
def reload_servers_config(servers: str | list[str]) -> None:
	"""Reloads the configuration of the specified servers."""

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
		frappe.msgprint(_("Configuration reloaded."), alert=True)


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Mail Server", ["cluster", "cluster_node_id"], constraint_name="unique_cluster_node_id"
	)
