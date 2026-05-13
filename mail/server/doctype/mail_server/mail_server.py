# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import io
import json
import os
import socket

import frappe
import paramiko
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.utils.dns import get_dns_record


class MailServer(Document):
	@property
	def ssh_public_key(self) -> str | None:
		"""Returns the SSH public key of the cluster."""

		return frappe.db.get_value("Mail Cluster", self.cluster, "ssh_public_key")

	def autoname(self) -> None:
		self.hostname = self.hostname.lower()
		self.name = self.hostname

	def validate(self) -> None:
		self.validate_hostname()
		self.validate_cluster()
		self.set_bootstrap_ndjson()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Server."))

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

	def set_bootstrap_ndjson(self) -> None:
		"""Sets the bootstrap NDJSON for the server."""

		if not self.bootstrap_ndjson:
			self.bootstrap_ndjson = self._generate_bootstrap_ndjson()

	@frappe.whitelist()
	def regenerate_bootstrap_ndjson(self) -> None:
		"""Regenerates the bootstrap NDJSON for the server."""

		frappe.only_for("System Manager")
		self.bootstrap_ndjson = self._generate_bootstrap_ndjson()
		self._db_set(bootstrap_ndjson=self.bootstrap_ndjson, notify=True)
		frappe.msgprint(_("Bootstrap NDJSON regenerated."), indicator="green", alert=True)

	def _generate_bootstrap_ndjson(self) -> str:
		"""Generates the bootstrap NDJSON for the server."""

		cluster = frappe.get_doc("Mail Cluster", self.cluster)
		operations = cluster.get_bootstrap_operations(self.hostname)

		return "\n".join([json.dumps(op) for op in operations])

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

		job = frappe.new_doc("Server Job")
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

	def _install_stalwart(self) -> None:
		"""Installs Stalwart on the Mail Server."""

		deployment = frappe.new_doc("Server Deployment")
		deployment.status = "Pending"
		deployment.server = self.name
		deployment.max_retries = 0
		deployment.insert(ignore_permissions=True)

	def _get_stalwart_env(
		self,
		recovery_mode: bool = False,
		role: str | None = None,
		push_shard: str | None = None,
		as_dict: bool = False,
	) -> str | dict:
		"""Returns the environment variables for Stalwart."""

		cluster = frappe.get_doc("Mail Cluster", self.cluster)
		env = {
			"STALWART_HOSTNAME": self.hostname,
			"STALWART_RECOVERY_MODE": cint(recovery_mode),
			"STALWART_RECOVERY_MODE_PORT": cint(self.recovery_http_port),
			"STALWART_RECOVERY_MODE_LOG_LEVEL": "debug",
			"STALWART_RECOVERY_ADMIN": f"{cluster.recovery_admin_user}:{cluster.get_password('recovery_admin_password')}",
		}

		if cluster.base_url:
			env["STALWART_PUBLIC_URL"] = cluster.base_url
		if role:
			env["STALWART_ROLE"] = role
		if push_shard:
			env["STALWART_PUSH_SHARD"] = push_shard

		if as_dict:
			return env

		return "\n".join([f"{key}={value}" for key, value in env.items()])

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)
