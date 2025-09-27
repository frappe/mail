# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import hashlib
import json
import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now, time_diff_in_seconds
from uuid_utils import uuid7

from mail.utils import get_mail_app_path


class MailServerDeployment(Document):
	@property
	def started_after(self) -> float:
		"""Returns the time taken to start the deployment in seconds."""

		if self.started_at and self.creation:
			started_after = time_diff_in_seconds(self.started_at, self.creation)
			if started_after > 0:
				return started_after

		return 0.0

	@property
	def duration(self) -> float:
		"""Returns the duration of the deployment in seconds."""

		if self.started_at and self.ended_at:
			duration = time_diff_in_seconds(self.ended_at, self.started_at)
			if duration > 0:
				return duration

		return 0.0

	@property
	def config_toml(self) -> str | None:
		"""Returns the config.toml content."""

		if self.config:
			return frappe.get_doc("Mail Server Config", self.config).config

	@property
	def port_mappings(self) -> list[str]:
		"""Returns the port mappings for the Mail Server."""

		server = frappe.get_doc("Mail Server", self.server)
		cluster = frappe.get_doc("Mail Cluster", server.cluster)

		port_mappings = []
		for listener in server.listeners or cluster.listeners:
			port = listener.bind.split(":")[-1]
			port_mappings.append(f"{port}:{port}")

		return port_mappings

	@property
	def compose_template_path(self) -> str:
		"""Returns the path to the docker-compose template."""

		return os.path.join(get_mail_app_path(), "mail/utils/docker/templates/docker-compose.yml.j2")

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_status()
		self.validate_server()
		self.validate_config()
		self.validate_config_checksum()

	def after_insert(self) -> None:
		if frappe.flags.do_not_enqueue:
			self.execute()
		else:
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"execute",
				queue="long",
				enqueue_after_commit=True,
			)

	def validate_status(self) -> None:
		"""Sets the status to 'Pending' if not set."""

		if not self.status:
			self.status = "Pending"

	def validate_server(self) -> None:
		"""Validate if the mail server is enabled."""

		if not frappe.db.get_value("Mail Server", self.server, "enabled"):
			frappe.throw(_("Mail Server {0} is disabled").format(self.server))
		elif not frappe.db.get_value("Mail Server", self.server, "ssh_verified"):
			frappe.throw(_("Please verify SSH connection for Mail Server {0}").format(self.server))

	def validate_config(self) -> None:
		"""Validates if the config belongs to the selected server."""

		if not self.config:
			frappe.throw(_("Config is required."))

		config_server = frappe.db.get_value("Mail Server Config", self.config, "server")
		if config_server != self.server:
			frappe.throw(_("Config does not belong to the selected server."))

	def validate_config_checksum(self) -> None:
		"""Sets the config checksum if not set."""

		if not self.config_checksum:
			self.config_checksum = hashlib.sha256(self.config_toml.encode("utf-8")).hexdigest()

	def execute(self) -> None:
		"""Executes the Ansible playbook."""

		kwargs = {}
		self._db_set(status="Running", started_at=now(), error_log=None, commit=True, notify=True)

		try:
			self.validate_server()

			playbook_kwargs = {
				"server_hostname": frappe.db.get_value("Mail Server", self.server, "hostname"),
				"config_toml": self.config_toml,
				"port_mappings": self.port_mappings,
				"compose_template_path": self.compose_template_path,
			}
			pb = frappe.new_doc("Mail Server Playbook")
			pb.status = "Pending"
			pb.server = self.server
			pb.max_retries = 0
			pb.playbook = "deploy-mail-server.yml"
			pb.playbook_kwargs = json.dumps(playbook_kwargs)
			frappe.flags.do_not_enqueue = True
			pb.insert(ignore_permissions=True)

			kwargs.update(
				{
					"status": pb.status,
					"stdout": pb.stdout,
					"stderr": pb.stderr,
					"exit_code": cint(pb.exit_code),
				}
			)

			if kwargs["status"] == "Failed":
				kwargs["retries"] = cint(self.retries) + 1

		except Exception:
			retries = cint(self.retries) + 1
			kwargs.update(
				{
					"status": "Failed",
					"retries": retries,
					"error_log": frappe.get_traceback(with_context=True),
				}
			)

		self._db_set(notify=True, ended_at=now(), **kwargs)

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retries a failed deployment."""

		frappe.only_for("System Manager")

		if self.status != "Failed":
			frappe.throw(_("Only failed deployments can be retried."))

		self._db_set(status="Pending", notify=True)

		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"execute",
			queue="long",
			enqueue_after_commit=True,
		)

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)
