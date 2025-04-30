# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import base64
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import random_string

from mail.mail.doctype.mail_server.mail_server import create_or_update_spf_dns_record
from mail.mail_server import MailServerAPI, Principal
from mail.utils import generate_secret, hash_password
from mail.utils.dns import get_dns_record
from mail.utils.validation import is_valid_cron_expression

DEFAULT_STORES = [
	{
		"type": "RocksDB",
		"store_id": "rocksdb",
		"path": "/opt/stalwart-mail/data",
		"compression": "LZ4",
		"min_blob_size": 16834,
		"write_buffer_size": 128,
		"purge_frequency": "0 3 * * *",
	}
]
DEFAULT_LISTENERS = [
	{"protocol": "HTTP", "listener_id": "http", "bind": "[::]:8080", "tls_implicit": 0},
	{"protocol": "HTTP", "listener_id": "https", "bind": "[::]:443", "tls_implicit": 1},
	{"protocol": "IMAP4", "listener_id": "imap", "bind": "[::]:143", "tls_implicit": 0},
	{"protocol": "IMAP4", "listener_id": "imaptls", "bind": "[::]:993", "tls_implicit": 1},
	{"protocol": "POP3", "listener_id": "pop3", "bind": "[::]:110", "tls_implicit": 0},
	{"protocol": "POP3", "listener_id": "pop3s", "bind": "[::]:995", "tls_implicit": 1},
	{
		"protocol": "ManageSieve",
		"listener_id": "sieve",
		"bind": "[::]:4190",
		"tls_implicit": 0,
	},
	{"protocol": "SMTP", "listener_id": "smtp", "bind": "[::]:25", "tls_implicit": 0},
	{
		"protocol": "SMTP",
		"listener_id": "submission",
		"bind": "[::]:587",
		"tls_implicit": 0,
	},
	{
		"protocol": "SMTP",
		"listener_id": "submissions",
		"bind": "[::]:465",
		"tls_implicit": 1,
	},
]
STORAGE_OPTIONS = {
	"storage_directory": ["RocksDB", "FoundationDB", "PostgreSQL", "mySQL", "SQLite"],
	"storage_data": ["RocksDB", "FoundationDB", "PostgreSQL", "mySQL", "SQLite"],
	"storage_blob": [
		"RocksDB",
		"FoundationDB",
		"PostgreSQL",
		"mySQL",
		"SQLite",
		"S3-compatible",
		"Azure Blob Storage",
		"Filesystem",
	],
	"storage_fts": ["RocksDB", "FoundationDB", "PostgreSQL", "mySQL", "SQLite", "ElasticSearch"],
	"storage_lookup": ["RocksDB", "FoundationDB", "PostgreSQL", "mySQL", "SQLite", "Redis/Memcached"],
}


class MailCluster(Document):
	def autoname(self) -> None:
		self.hostname = self.hostname.lower()
		self.name = self.hostname

	def validate(self) -> None:
		self.validate_enabled()
		self.validate_public()
		self.validate_hostname()
		self.validate_priority()
		self.validate_fallback_admin_password()
		self.generate_fallback_admin_secret()
		self.validate_base_url()
		self.validate_cluster_key()
		self.validate_stores()
		self.validate_storage()
		self.validate_listeners()

	def on_update(self) -> None:
		if self.has_value_changed("enabled") or self.has_value_changed("outbound"):
			create_or_update_spf_dns_record()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Cluster."))

		if self.outbound:
			self.db_set("enabled", 0)
			create_or_update_spf_dns_record()

	def validate_enabled(self) -> None:
		"""Validates the enabled status of the cluster."""

		if self.enabled and not self.inbound and not self.outbound:
			self.enabled = 0

		if self.enabled:
			return

		if tenant := frappe.db.exists("Mail Tenant", {"cluster": self.name}):
			frappe.throw(_("Mail Tenant {0} is using this cluster.").format(frappe.bold(tenant)))
		elif server := frappe.db.exists("Mail Server", {"enabled": 1, "cluster": self.name}):
			frappe.throw(
				_("Mail Server {0} is enabled. Please disable it first.").format(frappe.bold(server))
			)

	def validate_public(self) -> None:
		"""Validates the public status of the cluster."""

		if not self.public and not bool(
			frappe.db.count("Mail Cluster", {"enabled": 1, "public": 1, "name": ["!=", self.name]})
		):
			self.public = 1
			frappe.msgprint(
				_("At least one public cluster must be enabled. This cluster has been made public."),
				alert=True,
			)

	def validate_hostname(self) -> None:
		"""Validates the cluster and fetches the IP addresses."""

		if self.is_new() and frappe.db.exists("Mail Cluster", self.hostname):
			frappe.throw(_("Mail Cluster {0} already exists.").format(frappe.bold(self.hostname)))

		self.ipv4_addresses = "\n".join([r.address for r in get_dns_record(self.hostname, "A") or []])
		self.ipv6_addresses = "\n".join([r.address for r in get_dns_record(self.hostname, "AAAA") or []])

	def validate_priority(self) -> None:
		"""Validates the priority of the cluster."""

		if frappe.db.exists(
			"Mail Cluster",
			{"enabled": 1, "inbound": 1, "priority": self.priority, "name": ["!=", self.name]},
		):
			frappe.throw(
				_("Mail Cluster with priority {0} already exists.").format(frappe.bold(self.priority))
			)

	def validate_fallback_admin_password(self) -> None:
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

	def validate_cluster_key(self) -> None:
		"""Validates the encryption key of the cluster."""

		if not self.cluster_key:
			self.cluster_key = random_string(length=64)

	def validate_stores(self) -> None:
		"""Validates the stores."""

		store_ids = []
		for store in self.stores:
			if store.store_id in store_ids:
				frappe.throw(
					_("Row #{0}: Store ID {1} is duplicated.").format(store.idx, frappe.bold(store.store_id))
				)

			store_ids.append(store.store_id)

			if store.purge_frequency:
				is_valid_cron_expression(store.purge_frequency, raise_exception=True)

	def validate_storage(self) -> None:
		"""Validates the selected stores against the stores."""

		stores = {store.store_id: store for store in self.stores}
		storage_labels = get_storage_labels()

		for key in STORAGE_OPTIONS.keys():
			selected_storage = getattr(self, key)
			if selected_storage not in stores:
				frappe.throw(_("Store with Store ID {0} not found.").format(frappe.bold(selected_storage)))

			store = stores[selected_storage]
			if store.type not in STORAGE_OPTIONS[key]:
				frappe.throw(
					_("{0} has an invalid store type '{1}'. Allowed types are: {2}.").format(
						frappe.bold(storage_labels[key]),
						frappe.bold(store.type),
						", ".join(STORAGE_OPTIONS[key]),
					)
				)

		is_valid_cron_expression(self.jmap_account_purge_frequency, raise_exception=True)

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
	def initialize_defaults(self) -> None:
		"""Initializes the default values."""

		self.initialize_default_stores()
		self.initialize_default_listeners()

	def initialize_default_stores(self) -> None:
		"""Initializes the default stores."""

		self.stores = []
		for store in DEFAULT_STORES:
			self.append("stores", store)

		if len(self.stores) == 1:
			primary_store = self.stores[0]

			for field in STORAGE_OPTIONS.keys():
				if primary_store.type in STORAGE_OPTIONS[field]:
					setattr(self, field, primary_store.store_id)

	def initialize_default_listeners(self) -> None:
		"""Initializes the default listeners."""

		self.listeners = []
		for listener in DEFAULT_LISTENERS:
			self.append("listeners", listener)

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
		server_api = MailServerAPI(
			self.base_url,
			username=self.fallback_admin_user,
			password=self.get_password("fallback_admin_password"),
		)
		response = server_api.request(method="POST", endpoint="/api/principal", json=principal.__dict__)
		response.raise_for_status()
		response_json = response.json()

		if error := response_json.get("error"):
			frappe.throw(error)

		return f"api_{base64.b64encode(f'{name}:{secret}'.encode()).decode()}"

	@frappe.whitelist()
	def reload_servers_config(self) -> None:
		"""Reloads the Mail Cluster servers configuration."""

		frappe.only_for("System Manager")

		if not self.enabled:
			frappe.throw(_("Mail Cluster {0} is disabled.").format(frappe.bold(self.name)))

		servers = frappe.db.get_all("Mail Server", filters={"cluster": self.name, "enabled": 1}, pluck="name")
		for server in servers:
			server = frappe.get_cached_doc("Mail Server", server)
			server.reload_config()


@frappe.whitelist()
def reload_servers_config(clusters: str | list[str]) -> None:
	"""Reloads the Mail Cluster servers configuration."""

	frappe.only_for("System Manager")

	if isinstance(clusters, str):
		clusters = json.loads(clusters)

	reloaded_clusters = []
	for cluster in clusters:
		cluster = frappe.get_cached_doc("Mail Cluster", cluster)
		if cluster.enabled:
			cluster.reload_servers_config()
			reloaded_clusters.append(cluster.name)
		else:
			frappe.msgprint(_("Mail Cluster {0} is disabled.").format(frappe.bold(cluster.name)), alert=True)

	if reloaded_clusters:
		frappe.msgprint(_("Servers Configuration reloaded."), alert=True)


def get_storage_labels() -> dict:
	"""Returns the storage labels."""

	return {
		"storage_directory": _("Directory Storage"),
		"storage_data": _("Data Storage"),
		"storage_blob": _("Blob Storage"),
		"storage_fts": _("Full Text Index Storage"),
		"storage_lookup": _("In-Memory Storage"),
	}
