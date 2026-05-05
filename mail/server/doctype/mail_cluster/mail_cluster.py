# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import base64
import io
import json

import frappe
import paramiko
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, random_string

from mail.backend import MailBackendAPI, Principal
from mail.jmap.connection import raise_for_status
from mail.utils import generate_secret, hash_password
from mail.utils.dns import get_dns_record

DEFAULT_TRACES = [
	{
		"tracer_id": "log",
		"type": "Log file",
		"level": "Info",
		"path": "/opt/stalwart/logs",
		"prefix": "stalwart.log",
		"rotate": "Daily",
	}
]


class MailCluster(Document):
	@property
	def config(self) -> str:
		"""Returns the configuration for the cluster."""

		if not self.store_type:
			return "{}"

		config = {"@type": self.store_type}

		if self.store_type == "RocksDb":
			config.update(
				{
					"path": self.store_path,
					"blobSize": cint(self.store_blob_size),
					"bufferSize": cint(self.store_buffer_size),
					"poolWorkers": cint(self.store_pool_workers),
				}
			)

		elif self.store_type == "Sqlite":
			config.update(
				{
					"path": self.store_path,
					"poolWorkers": cint(self.store_pool_workers),
					"poolMaxConnections": cint(self.store_pool_max_connections),
				}
			)

		elif self.store_type == "FoundationDb":
			config.update(
				{
					"clusterFile": self.store_cluster_file,
					"datacenterId": self.store_datacenter_id,
					"machineId": self.store_machine_id,
					"transactionRetryDelay": cint(self.store_transaction_retry_delay),
					"transactionRetryLimit": cint(self.store_transaction_retry_limit),
					"transactionTimeout": cint(self.store_transaction_timeout),
				}
			)

		elif self.store_type == "PostgreSql":
			config.update(
				{
					"timeout": cint(self.store_timeout),
					"useTls": cint(self.store_use_tls),
					"allowInvalidCerts": cint(self.store_allow_invalid_certs),
					"poolMaxConnections": cint(self.store_pool_max_connections),
					"poolRecyclingMethod": self.store_pool_recycling_method,
					"host": self.store_host,
					"port": cint(self.store_port),
					"database": self.store_database,
					"authUsername": self.store_auth_username,
					"authSecret": self.get_password("store_auth_secret") if self.store_auth_secret else None,
					"options": self.store_options,
				}
			)

		elif self.store_type == "MySql":
			config.update(
				{
					"timeout": cint(self.store_timeout),
					"useTls": cint(self.store_use_tls),
					"allowInvalidCerts": cint(self.store_allow_invalid_certs),
					"maxAllowedPacket": cint(self.store_max_allowed_packet),
					"poolMaxConnections": cint(self.store_pool_max_connections),
					"poolMinConnections": cint(self.store_pool_min_connections),
					"host": self.store_host,
					"port": cint(self.store_port),
					"database": self.store_database,
					"authUsername": self.store_auth_username,
					"authSecret": self.get_password("store_auth_secret") if self.store_auth_secret else None,
				}
			)

		return json.dumps(config, indent=4)

	def autoname(self) -> None:
		self.hostname = self.hostname.lower()
		self.name = self.hostname

	def validate(self) -> None:
		self.validate_enabled()
		self.validate_hostname()
		self.validate_fallback_admin_password()
		self.generate_fallback_admin_secret()
		self.validate_base_url()
		self.validate_traces()

	def before_insert(self) -> None:
		self.generate_ssh_keypair()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Cluster."))

	def validate_enabled(self) -> None:
		"""Validates the enabled status of the cluster."""

		if self.enabled:
			return

		if server := frappe.db.exists("Mail Server", {"enabled": 1, "cluster": self.name}):
			frappe.throw(
				_("Mail Server {0} is enabled. Please disable it first.").format(frappe.bold(server))
			)

	def validate_hostname(self) -> None:
		"""Validates the cluster and fetches the IP addresses."""

		if self.is_new() and frappe.db.exists("Mail Cluster", self.hostname):
			frappe.throw(_("Mail Cluster {0} already exists.").format(frappe.bold(self.hostname)))

		self.ipv4_addresses = "\n".join([r.address for r in get_dns_record(self.hostname, "A") or []])
		self.ipv6_addresses = "\n".join([r.address for r in get_dns_record(self.hostname, "AAAA") or []])

	def validate_fallback_admin_password(self) -> None:
		"""Validates the fallback admin password."""

		if self.fallback_admin_password:
			if len(self.fallback_admin_password) < 16:
				frappe.throw(_("Password must be at least 16 characters long."))
		else:
			self.fallback_admin_password = random_string(length=20)

	def generate_fallback_admin_secret(self) -> None:
		"""Generates the fallback admin secret."""

		if self.has_value_changed("fallback_admin_password"):
			self.fallback_admin_secret = hash_password(self.get_password("fallback_admin_password"))

	def validate_base_url(self) -> None:
		"""Validates the base URL of the cluster."""

		if not self.base_url:
			self.base_url = f"https://{self.hostname}/"

	def validate_traces(self) -> None:
		"""Validates the traces."""

		tracer_ids = []
		for trace in self.traces:
			if trace.tracer_id in tracer_ids:
				frappe.throw(
					_("Row #{0}: Tracer ID {1} is duplicated.").format(
						trace.idx, frappe.bold(trace.tracer_id)
					)
				)

			tracer_ids.append(trace.tracer_id)

	def generate_ssh_keypair(self, save: bool = False) -> None:
		"""Generates an SSH key pair for the cluster."""

		key = paramiko.RSAKey.generate(4096)
		private_io = io.StringIO()
		key.write_private_key(private_io)
		self.ssh_private_key = private_io.getvalue()
		self.ssh_public_key = f"{key.get_name()} {key.get_base64()} frappe-mail-cluster"

		if save:
			self.save()

	@frappe.whitelist()
	def initialize_defaults(self) -> None:
		"""Initializes the default values."""

		self.initialize_store()
		self.initialize_default_traces()

	def initialize_store(self) -> None:
		"""Initializes the default store configuration."""

		if not self.store_type:
			self.store_type = "RocksDb"
			self.store_path = "/var/lib/stalwart/rocksdb"
			self.store_blob_size = 16834
			self.store_buffer_size = 134217728
			self.store_pool_workers = 0

	def initialize_default_traces(self) -> None:
		"""Initializes the default traces."""

		self.traces = []
		for trace in DEFAULT_TRACES:
			self.append("traces", trace)

	@frappe.whitelist()
	def get_fallback_admin_password(self) -> str:
		"""Returns the admin password of the cluster."""

		frappe.only_for("System Manager")
		return self.get_password("fallback_admin_password")

	@frappe.whitelist()
	def generate_api_key(self) -> None:
		"""Generates an API key for the cluster."""

		frappe.only_for("System Manager")
		self.api_key = self._generate_api_key()
		self.save()

	def _generate_api_key(self) -> str:
		"""Generates an API key for the cluster."""

		if not self.base_url:
			frappe.throw(_("Base URL is required."))

		name = f"{random_string(10)}-{self.hostname}".lower()
		secret = generate_secret()
		principal = Principal(
			name=name, type="apiKey", secrets=secret, roles=["admin"], enabledPermissions=["authenticate"]
		)
		backend_api = MailBackendAPI(
			self.base_url,
			username=self.fallback_admin_user,
			password=self.get_password("fallback_admin_password"),
		)
		response = backend_api.request(method="POST", endpoint="/api/principal", json=principal.__dict__)
		raise_for_status(response)
		response_json = response.json()

		if error := response_json.get("error"):
			frappe.throw(error)

		return f"api_{base64.b64encode(f'{name}:{secret}'.encode()).decode()}"


def get_storage_labels() -> dict:
	"""Returns the storage labels."""

	return {
		"storage_directory": _("Directory Storage"),
		"storage_data": _("Data Storage"),
		"storage_blob": _("Blob Storage"),
		"storage_fts": _("Full Text Index Storage"),
		"storage_lookup": _("In-Memory Storage"),
	}
