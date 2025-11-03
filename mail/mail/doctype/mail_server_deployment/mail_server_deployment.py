# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import hashlib
import json
import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils import cint, now, time_diff_in_seconds
from uuid_utils import uuid7


class MailServerDeployment(Document):
	@property
	def config_toml(self) -> str | None:
		"""Returns the config.toml content."""

		if self.config:
			return frappe.get_doc("Mail Server Config", self.config).config

	@property
	def docker_compose(self) -> str | None:
		"""Returns the docker-compose.yml content."""

		if self.services:
			docker_compose = "services:\n"
			for service in self.services:
				docker_compose += f"  {service.service}:\n"
				docker_compose += f"    image: {service.image}\n"
				docker_compose += f"    container_name: {service.container}\n"
				docker_compose += f"    restart: {service.restart}\n"
				docker_compose += f"    network_mode: {service.network_mode}\n"

				depends_on = json.loads(service.depends_on) if service.depends_on else []
				if depends_on:
					docker_compose += "    depends_on:\n"
					for dependency in depends_on:
						docker_compose += f"      - {dependency}\n"

				ports = json.loads(service.ports) if service.ports else []
				if ports:
					docker_compose += "    ports:\n"
					for port in ports:
						docker_compose += f'      - "{port}"\n'

				volumes = json.loads(service.volumes) if service.volumes else []
				if volumes:
					docker_compose += "    volumes:\n"
					for volume in volumes:
						docker_compose += f"      - {volume}\n"

			return docker_compose

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_status()
		self.validate_server()
		self.validate_config()
		self.validate_config_checksum()
		self.validate_services()

	def after_insert(self) -> None:
		if frappe.flags.do_not_enqueue:
			self.execute()
		else:
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"execute",
				queue="long",
				timeout=cint(frappe.conf.server_deployment_timeout) or 1500,
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

	def validate_services(self) -> None:
		"""Validates and prepares the services for deployment."""

		server_hostname = frappe.db.get_value("Mail Server", self.server, "hostname")
		services = {
			"stalwart": {
				"image": "stalwartlabs/stalwart:latest",
				"container": f"stalwart_{server_hostname}",
				"restart": "unless-stopped",
				"network_mode": "host",
				"depends_on": json.dumps(["redis"] if self.install_redis else [], indent=4),
				"ports": json.dumps([], indent=4),
				"volumes": json.dumps(["{{ stalwart_root }}:/opt/stalwart"], indent=4),
			}
		}

		if self.install_redis:
			services["redis"] = {
				"image": "redis:7-alpine",
				"container": f"redis_{server_hostname}",
				"restart": "unless-stopped",
				"network_mode": "host",
				"depends_on": json.dumps([], indent=4),
				"ports": json.dumps([], indent=4),
				"volumes": json.dumps(["{{ stalwart_root }}/redis:/opt/stalwart/redis"], indent=4),
			}

		for service in self.services:
			services[service.service] = {
				"image": service.image,
				"container": service.container,
				"restart": service.restart,
				"network_mode": service.network_mode,
				"depends_on": json.dumps(
					json.loads(service.depends_on) if service.depends_on else [], indent=4
				),
				"ports": json.dumps(json.loads(service.ports) if service.ports else [], indent=4),
				"volumes": json.dumps(json.loads(service.volumes) if service.volumes else [], indent=4),
			}

		self.services = []
		for name, service in services.items():
			service["service"] = name
			self.append("services", service)

	def execute(self) -> None:
		"""Executes the deployment."""

		kwargs = {}
		started_at = now()
		self._db_set(
			status="Running",
			started_at=started_at,
			started_after=time_diff_in_seconds(started_at, self.creation),
			error_log=None,
			commit=True,
			notify=True,
		)

		try:
			self.validate_server()

			variables = {
				"server_hostname": frappe.db.get_value("Mail Server", self.server, "hostname"),
				"config_toml": self.config_toml,
				"docker_compose": self.docker_compose,
				"install_redis": cint(self.install_redis),
			}
			play = frappe.new_doc("Mail Server Ansible Play")
			play.status = "Pending"
			play.server = self.server
			play.deployment = self.name
			play.max_retries = 0
			play.play = "Deploy Mail Server"
			play.playbook = "deploy-mail-server.yml"

			for key, value in variables.items():
				if isinstance(value, int | bool):
					value = str(value)
				elif isinstance(value, list | dict):
					value = json.dumps(value, indent=4)

				play.append("variables", {"key_": key, "value": value})

			frappe.flags.do_not_enqueue = True
			play.insert(ignore_permissions=True)

			kwargs.update(
				{
					"status": play.status,
					"error_log": play.error_log,
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

		ended_at = now()
		self._db_set(
			ended_at=ended_at, duration=time_diff_in_seconds(ended_at, started_at), notify=True, **kwargs
		)

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
			timeout=cint(frappe.conf.ansible_play_timeout) or 1500,
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


def retry_failed_deployments() -> None:
	"""Called by the scheduler to retry failed deployments."""

	MSD = frappe.qb.DocType("Mail Server Deployment")
	deployments = (
		frappe.qb.from_(MSD)
		.select(MSD.name)
		.where((MSD.status == "Failed") & (MSD.retries > 0) & (MSD.retries < MSD.max_retries))
		.orderby(MSD.creation, order=Order.asc)
	).run(pluck="name")

	if not deployments:
		return

	for deployment in deployments:
		doc = frappe.get_doc("Mail Server Deployment", deployment)
		doc.retry()
