# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import base64
import hashlib
import io
import json

import frappe
import paramiko
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils import cint, random_string

from mail.backend import MailBackendAPI, Principal
from mail.jmap.connection import raise_for_status
from mail.server.doctype.dns_record.dns_record import create_or_update_dns_record
from mail.utils import generate_secret, get_mail_config, get_spf_host_for_cluster, hash_password
from mail.utils.dns import get_dns_record
from mail.utils.validation import is_valid_cron_expression

DEFAULT_STORES = [
	{
		"type": "RocksDB",
		"store_id": "rocksdb",
		"path": "/opt/stalwart/data",
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
		"bind": "[::]:587\n[::]:8025",
		"tls_implicit": 0,
	},
	{
		"protocol": "SMTP",
		"listener_id": "submissions",
		"bind": "[::]:465\n[::]:2525",
		"tls_implicit": 1,
	},
]
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
		self.validate_spf_identifier()
		self.validate_fallback_admin_password()
		self.generate_fallback_admin_secret()
		self.validate_base_url()
		self.validate_stores()
		self.validate_storage()
		self.validate_listeners()
		self.validate_traces()

	def before_insert(self) -> None:
		self.generate_ssh_keypair()

	def on_update(self) -> None:
		if self.has_value_changed("enabled"):
			create_or_update_spf_dns_record_for_cluster(self.name)

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Cluster."))

		self.db_set("enabled", 0)
		create_or_update_spf_dns_record_for_cluster(self.name)

	def validate_enabled(self) -> None:
		"""Validates the enabled status of the cluster."""

		if self.enabled:
			return

		if server := frappe.db.exists("Mail Server", {"enabled": 1, "cluster": self.name}):
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

	def validate_spf_identifier(self) -> None:
		"""Validates the SPF identifier of the cluster."""

		if not self.spf_identifier:
			self.spf_identifier = (
				base64.b32encode(hashlib.sha256(self.hostname.encode()).digest()).decode("ascii").lower()[:10]
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

		is_valid_cron_expression(self.account_purge_frequency, raise_exception=True)

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

		self.initialize_default_stores()
		self.initialize_default_listeners()
		self.initialize_default_traces()

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


def create_or_update_spf_dns_record_for_cluster(cluster: str) -> None:
	"""Creates or updates the SPF DNS record for the cluster."""

	spf_host = get_spf_host_for_cluster(cluster)
	default_ttl = cint(get_mail_config("default_dns_ttl"))

	SERVER = frappe.qb.DocType("Mail Server")
	CLUSTER = frappe.qb.DocType("Mail Cluster")
	outbound_servers = (
		frappe.qb.from_(CLUSTER)
		.join(SERVER)
		.on(CLUSTER.name == SERVER.cluster)
		.select(SERVER.name)
		.where(
			(CLUSTER.enabled == 1)
			& (CLUSTER.name == cluster)
			& (SERVER.enabled == 1)
			& (SERVER.include_in_spf_record == 1)
		)
		.orderby(SERVER.name, order=Order.asc)
	).run(pluck="name")

	if outbound_servers:
		outbound_servers = [f"a:{outbound_server}" for outbound_server in outbound_servers]
		create_or_update_dns_record(
			host=spf_host,
			type="TXT",
			value=f"v=spf1 {' '.join(outbound_servers)} ~all",
			ttl=default_ttl,
			category="Server Record",
		)
	elif spf_dns_record := frappe.db.exists("DNS Record", {"host": spf_host, "type": "TXT"}):
		frappe.delete_doc("DNS Record", spf_dns_record, ignore_permissions=True)
