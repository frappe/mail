# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import base64
import io
import json

import frappe
import paramiko
from frappe import _
from frappe.model.document import Document
from frappe.utils import random_string

from mail.backend import MailBackendAPI, Principal
from mail.jmap.connection import raise_for_status
from mail.utils import generate_secret
from mail.utils.dns import get_dns_record

ALLOWED_STORE_TYPES = {
	"data_store": ["RocksDb", "Sqlite", "FoundationDb", "PostgreSql", "MySql"],
	"blob_store": ["RocksDb"],
	"search_store": ["RocksDb"],
	"in_memory_store": ["RocksDb"],
}


class MailCluster(Document):
	@property
	def data_store_config(self) -> str:
		if not self.data_store:
			return "{}"

		store = frappe.get_doc("Mail Cluster Store", self.data_store)
		return json.dumps(store.config, indent=4)

	@property
	def blob_store_config(self) -> str:
		if not self.blob_store:
			return '{"@type": "Default"}'

		store = frappe.get_doc("Mail Cluster Store", self.blob_store)
		return json.dumps(store.config, indent=4)

	@property
	def search_store_config(self) -> str:
		if not self.search_store:
			return '{"@type": "Default"}'

		store = frappe.get_doc("Mail Cluster Store", self.search_store)
		return json.dumps(store.config, indent=4)

	@property
	def in_memory_store_config(self) -> str:
		if not self.in_memory_store:
			return '{"@type": "Default"}'

		store = frappe.get_doc("Mail Cluster Store", self.in_memory_store)
		return json.dumps(store.config, indent=4)

	def autoname(self) -> None:
		self.hostname = self.hostname.lower()
		self.name = self.hostname

	def before_insert(self) -> None:
		self.generate_ssh_keypair()
		self.initialize_defaults()

	def validate(self) -> None:
		self.validate_enabled()
		self.validate_hostname()
		self.validate_default_domain()
		self.validate_recovery_admin_password()
		self.validate_base_url()
		self.validate_stores()

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

	def validate_default_domain(self) -> None:
		"""Validates the default domain of the cluster."""

		if not self.default_domain:
			self.default_domain = self.hostname

	def validate_recovery_admin_password(self) -> None:
		"""Validates the recovery admin password."""

		if self.recovery_admin_password:
			if len(self.recovery_admin_password) < 16:
				frappe.throw(_("Password must be at least 16 characters long."))
		else:
			self.recovery_admin_password = random_string(length=20)

	def validate_base_url(self) -> None:
		"""Validates the base URL of the cluster."""

		if not self.base_url:
			self.base_url = f"https://{self.hostname}/"

	def validate_stores(self) -> None:
		"""Validates the data stores of the cluster."""

		def validate_store(store_field: str, required: bool = False) -> None:
			store = self.get(store_field)

			if required and not store:
				frappe.throw(_("{0} is required.").format(self.meta.get_field(store_field).label))

			if not store:
				return

			if store_field != "data_store" and store == self.data_store:
				self.set(store_field, None)
				return

			store_type = frappe.db.get_value("Mail Cluster Store", store, "type")
			allowed_types = ALLOWED_STORE_TYPES[store_field]

			if store_type not in allowed_types:
				frappe.throw(
					_("{0} type must be one of {1}.").format(
						self.meta.get_field(store_field).label,
						", ".join(allowed_types),
					)
				)

		validate_store("data_store", required=True)

		for field in ["blob_store", "search_store", "in_memory_store"]:
			validate_store(field)

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

		self.initialize_data_store()

	def initialize_data_store(self) -> None:
		"""Initializes the data store for the cluster."""

		if not self.data_store:
			store = frappe.new_doc("Mail Cluster Store")
			store.type = "RocksDb"
			store.path = "/etc/stalwart/data"
			store.blob_size = 16834
			store.buffer_size = 134217728
			store.pool_workers = 1
			store.insert()

			self.data_store = store.name

	@frappe.whitelist()
	def get_recovery_admin_password(self) -> str:
		"""Returns the admin password of the cluster."""

		frappe.only_for("System Manager")
		return self.get_password("recovery_admin_password")

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
			username=self.recovery_admin_user,
			password=self.get_password("recovery_admin_password"),
		)
		response = backend_api.request(method="POST", endpoint="/api/principal", json=principal.__dict__)
		raise_for_status(response)
		response_json = response.json()

		if error := response_json.get("error"):
			frappe.throw(error)

		return f"api_{base64.b64encode(f'{name}:{secret}'.encode()).decode()}"

	def get_bootstrap_operations(self, hostname: str = "{{ hostname }}") -> list[dict]:
		"""Returns the bootstrap operations for the cluster."""

		operations = [
			{
				"@type": "update",
				"object": "Bootstrap",
				"id": "singleton",
				"value": {
					# required
					"serverHostname": hostname,
					"defaultDomain": self.default_domain,
					# optional
					"requestTlsCertificate": True,
					"generateDkimKeys": True,
					"dataStore": json.loads(self.data_store_config),
					"blobStore": json.loads(self.blob_store_config),
					"searchStore": json.loads(self.search_store_config),
					"inMemoryStore": json.loads(self.in_memory_store_config),
					"directory": {"@type": "Internal"},
					"tracer": {
						"@type": "Log",
						"ansi": True,
						"enable": True,
						"eventsPolicy": "exclude",
						"level": "info",
						"prefix": "stalwart",
						"rotate": "daily",
						"path": "/etc/stalwart/logs",
					},
					"dnsServer": {"@type": "Manual"},
				},
			}
		]

		return operations


def get_storage_labels() -> dict:
	"""Returns the storage labels."""

	return {
		"storage_directory": _("Directory Storage"),
		"storage_data": _("Data Storage"),
		"storage_blob": _("Blob Storage"),
		"storage_fts": _("Full Text Index Storage"),
		"storage_lookup": _("In-Memory Storage"),
	}
