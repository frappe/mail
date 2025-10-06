# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from uuid_utils import uuid7

from mail.backend import get_mail_backend_api
from mail.jmap import raise_for_status
from mail.utils import flatten_dict, password_or_none

LOCAL_KEYS = [
	"acme.*",
	"store.*",
	"directory.*",
	"tracer.*",
	"metrics.*",
	"!server.blocked-ip.*",
	"!server.allowed-ip.*",
	"server.*",
	"authentication.fallback-admin.*",
	"cluster.*",
	"config.local-keys.*",
	"storage.data",
	"storage.blob",
	"storage.lookup",
	"storage.fts",
	"storage.directory",
	"storage.full-text.*",
	"certificate.*",
	"account.purge.frequency",
	"jmap.email.*",
	"jmap.protocol.*",
	"jmap.mailbox.*",
	"jmap.push.*",
	"email.encryption.*",
	"email.auto-expunge",
	"changes.max-history",
	"enterprise.license-key",
]
STORE_TYPE_MAP = {
	"RocksDB": "rocksdb",
	"FoundationDB": "foundationdb",
	"PostgreSQL": "postgresql",
	"mySQL": "mysql",
	"SQLite": "sqlite",
	"S3-compatible": "s3",
	"Redis/Memcached": "redis",
	"ElasticSearch": "elasticsearch",
	"Azure Blob Storage": "azure",
	"Filesystem": "fs",
	"SQL with Replicas": "sql-read-replica",
	"Sharded Blob Store": "sharded-blob",
	"Sharded In-Memory Store": "sharded-in-memory",
}
PROTOCOL_MAP = {
	"SMTP": "smtp",
	"LMTP": "lmtp",
	"HTTP": "http",
	"IMAP4": "imap",
	"POP3": "pop3",
	"ManageSieve": "managesieve",
}


class MailServerConfig(Document):
	@property
	def config(self) -> str | None:
		"""Returns the TOML configuration for the Mail Server."""

		if self.flags.in_delete:
			return

		frappe.only_for("System Manager")

		if self.config_toml:
			return self.get_password("config_toml")

	def autoname(self) -> None:
		self.name = str(uuid7())

	def before_insert(self) -> None:
		self.generate_config_toml()

	def generate_config_toml(self) -> None:
		"""Generates the TOML configuration for the Mail Server."""

		self.config_toml = get_config_toml(self.server)

	@frappe.whitelist()
	def deploy(self) -> None:
		"""Deploys Stalwart with the current configuration."""

		frappe.only_for("System Manager")

		server = frappe.get_doc("Mail Server", self.server)
		server._install_stalwart(config=self.name)
		frappe.msgprint(_("Deploy of Stalwart initiated."), indicator="green", alert=True)

	@frappe.whitelist()
	def update_config_on_server(self) -> None:
		"""Updates the configuration on the Mail Server."""

		frappe.only_for("System Manager")

		values = []
		for cfg in self.get_password("config_toml").split("\n"):
			stripped = cfg.strip()
			if not stripped or stripped.startswith("#"):
				continue

			key, value = cfg.split("=", 1)
			key = key.strip()
			value = value.strip().strip('"')
			values.append([key, value])

		data = [
			{
				"type": "insert",
				"prefix": None,
				"values": values,
				"assert_empty": False,
			}
		]
		backend_api = get_mail_backend_api("Mail Server", self.server)
		response = backend_api.request("POST", "/api/settings", data=json.dumps(data))
		raise_for_status(response)

		if response_json := response.json():
			if response_json.get("error"):
				frappe.throw(
					title=_("Failed to update configuration"), msg=json.dumps(response_json, indent=4)
				)
			elif response_json.get("data") is None:
				frappe.msgprint(
					_("Configuration updated successfully."),
					alert=True,
					indicator="green",
				)
			else:
				frappe.msgprint(
					_(
						"Configuration updated successfully, but the response from the server was unexpected: {response}"
					).format(response=json.dumps(response_json))
				)


def create_mail_server_config(server: str) -> "MailServerConfig":
	"""Creates a new Mail Server Config."""

	config = frappe.new_doc("Mail Server Config")
	config.server = server
	config.insert()

	return config


def get_mail_server_config(server: str) -> MailServerConfig | None:
	"""Returns the Mail Server Config."""

	if config := frappe.db.exists("Mail Server Config", {"server": server}):
		return frappe.get_doc("Mail Server Config", config)


def get_config_toml(server: str) -> str | None:
	"""Returns the TOML configuration for the Mail Server."""

	def _format_value_or_zero(value: int, postfix: str) -> str | int:
		return f"{value}{postfix}" if value else 0

	def _wrap_in_triple_quotes(value: str) -> str:
		return f"'''{value}'''"

	def _split_lines(value: str) -> list:
		return value.split("\n")

	def _split_lines_or_empty(value: str) -> list:
		return _split_lines(value) if value else []

	def _format_keys(keys: list) -> dict:
		width = len(str(len(keys) - 1))
		return {str(i).zfill(width): key for i, key in enumerate(keys)}

	def _get_acme_config(acme) -> dict:
		config = {
			"default": bool(acme.default),
			"directory": acme.directory,
			"challenge": acme.challenge.lower(),
			"contact": _split_lines_or_empty(acme.contact),
			"domains": _split_lines_or_empty(acme.domains),
			"cache": "%{BASE_PATH}%/etc/acme",
			"renew-before": _format_value_or_zero(acme.renew_before, "d"),
			"eab": {"kid": acme.eab_kid, "hmac-key": password_or_none(acme, "eab_hmac_key")},
		}

		return {acme.directory_id: config}

	def _get_acme_providers(acme_providers: list) -> dict:
		return {k: v for acme in acme_providers for k, v in _get_acme_config(acme).items()}

	def _get_tls_config(tls) -> dict:
		cert = _wrap_in_triple_quotes(tls.cert) if tls.cert else f"%{{file:{tls.cert_path}}}%"
		private_key = (
			_wrap_in_triple_quotes(tls.private_key)
			if tls.private_key
			else f"%{{file:{tls.private_key_path}}}%"
		)
		config = {
			"default": bool(tls.default),
			"cert": cert,
			"private-key": private_key,
			"subjects": _split_lines_or_empty(tls.subjects),
		}

		return {tls.certificate_id: config}

	def _get_tls_certificates(tls_certificates: list) -> dict:
		return {k: v for tls in tls_certificates for k, v in _get_tls_config(tls).items()}

	def _get_listeners(listeners: list) -> dict:
		result = {}

		for listener in listeners:
			binds = _split_lines(listener.bind)
			result[listener.listener_id] = {
				"bind": _format_keys(binds) if len(binds) > 1 else binds[0],
				"protocol": PROTOCOL_MAP[listener.protocol],
				"tls": {"implicit": bool(listener.tls_implicit)},
			}

		return result

	def _get_local_keys(outbound_only: bool = False) -> dict:
		local_keys = LOCAL_KEYS + (
			["session.rcpt.directory", "queue.strategy.route"] if outbound_only else []
		)
		return _format_keys(local_keys)

	def _get_store_config(store) -> dict:
		config = {"type": STORE_TYPE_MAP[store.type]}

		if store.type in ["SQLite", "PostgreSQL", "mySQL"]:
			config.update({"pool": {"max-connections": store.pool_max_connections}})

		if store.type in ["S3-compatible", "Azure Blob Storage"]:
			config.update({"key-prefix": store.key_prefix, "max-retries": store.max_retries})

		if store.type in ["PostgreSQL", "mySQL", "Redis/Memcached", "ElasticSearch"]:
			if not (store.type == "Redis/Memcached" and store.redis_type == "Redis Single Node"):
				config.update({"user": store.user, "password": password_or_none(store, "password")})

		if store.type in ["PostgreSQL", "mySQL", "S3-compatible", "Redis/Memcached", "Azure Blob Storage"]:
			config["timeout"] = _format_value_or_zero(store.timeout, "s")

		if store.type in [
			"RocksDB",
			"SQLite",
			"Filesystem",
			"FoundationDB",
			"PostgreSQL",
			"mySQL",
			"S3-compatible",
			"Azure Blob Storage",
		]:
			config.update(
				{
					"compression": store.compression.lower(),
					"purge": {"frequency": store.purge_frequency},
				}
			)

		match store.type:
			case "RocksDB" | "SQLite" | "Filesystem":
				config["path"] = store.path

				if store.type in ["RocksDB", "SQLite"]:
					config["workers"] = store.workers

				if store.type == "RocksDB":
					config.update(
						{
							"min-blob-size": store.min_blob_size,
							"write-buffer-size": store.write_buffer_size,
						}
					)
				elif store.type == "Filesystem":
					config["depth"] = store.depth

			case "FoundationDB":
				config.update(
					{
						"cluster-file": store.cluster_file,
						"transaction": {
							"timeout": _format_value_or_zero(store.transaction_timeout, "s"),
							"retry-limit": store.transaction_retry_limit,
							"max-retry-delay": _format_value_or_zero(store.transaction_max_retry_delay, "s"),
						},
						"ids": {
							"machine": store.machine,
							"datacenter": store.datacenter,
						},
					}
				)

			case "PostgreSQL" | "mySQL":
				config.update(
					{
						"host": store.host,
						"port": store.port,
						"database": store.database,
						"tls": {
							"enable": bool(store.tls_enable),
							"allow-invalid-certs": bool(store.tls_allow_invalid_certs),
						},
					}
				)

				if store.type == "mySQL":
					config["max-allowed-packet"] = store.max_allowed_packet
					config["pool"]["min-connections"] = store.pool_min_connections

			case "S3-compatible":
				config.update(
					{
						"region": store.region,
						"endpoint": store.endpoint,
						"profile": store.profile,
						"bucket": store.bucket,
						"access-key": password_or_none(store, "access_key"),
						"secret-key": password_or_none(store, "secret_key"),
						"security-token": password_or_none(store, "security_token"),
					}
				)

			case "Redis/Memcached":
				redis_type = "single" if store.redis_type == "Redis Single Node" else "cluster"
				config.update(
					{
						"redis-type": redis_type,
						"urls": _split_lines_or_empty(store.urls),
					}
				)

				if redis_type == "cluster":
					config.update(
						{
							"read-from-replicas": bool(store.read_from_replicas),
							"retry": {
								"total": store.retry_total,
								"max-wait": _format_value_or_zero(store.retry_max_wait, "ms"),
								"min-wait": _format_value_or_zero(store.retry_min_wait, "ms"),
							},
						}
					)

			case "ElasticSearch":
				config.update(
					{
						"url": store.url,
						"cloud-id": store.cloud_id,
						"tls": {"allow-invalid-certs": bool(store.tls_allow_invalid_certs)},
						"index": {
							"shards": store.index_shards,
							"replicas": store.index_replicas,
						},
					}
				)

			case "Azure Blob Storage":
				config.update(
					{
						"storage-account": store.storage_account,
						"container": store.container,
						"azure-access-key": password_or_none(store, "azure_access_key"),
						"sas-token": password_or_none(store, "sas_token"),
					}
				)

		return {store.store_id: config}

	def _get_stores(stores: list) -> dict:
		return {k: v for store in stores for k, v in _get_store_config(store).items()}

	def _get_traces(traces: list) -> dict:
		result = {}
		trace_types = {
			"Log file": "log",
			"Console": "console",
			"Systemd Journal": "journal",
			"Open Telemetry": "open-telemetry",
		}

		for trace in traces:
			result[trace.tracer_id] = {
				"enable": True,
				"type": trace_types[trace.type],
				"level": trace.level.lower(),
				"lossy": bool(trace.lossy),
			}

			if trace.type == "Log file":
				result[trace.tracer_id].update(
					{
						"path": trace.path,
						"prefix": trace.prefix,
						"rotate": trace.rotate.lower(),
						"ansi": bool(trace.ansi),
						"multiline": bool(trace.multiline),
					}
				)
			elif trace.type == "Console":
				result[trace.tracer_id].update(
					{
						"ansi": bool(trace.ansi),
						"multiline": bool(trace.multiline),
						"buffer": bool(trace.buffer),
					}
				)
			elif trace.type == "Open Telemetry":
				result[trace.tracer_id].update(
					{
						"transport": trace.transport.lower(),
						"endpoint": trace.endpoint,
						"timeout": _format_value_or_zero(trace.timeout, "s"),
						"throttle": _format_value_or_zero(trace.throttle, "ms"),
						"enable": {
							"log-exporter": bool(trace.enable_log_exporter),
							"span-exporter": bool(trace.enable_span_exporter),
						},
					}
				)

		return result

	server = frappe.get_doc("Mail Server", server)
	cluster = frappe.get_doc("Mail Cluster", server.cluster)

	config = {
		"authentication": {
			"fallback-admin": {
				"user": cluster.fallback_admin_user,
				"secret": cluster.fallback_admin_secret,
			}
		},
		"acme": _get_acme_providers(server.acme_providers),
		"certificate": _get_tls_certificates(server.tls_certificates),
		"server": {
			"hostname": server.hostname,
			"proxy": {"trusted-networks": _split_lines_or_empty(cluster.server_proxy_trusted_networks)},
			"max-connections": server.server_max_connections,
			"listener": _get_listeners(server.listeners or cluster.listeners),
			"socket": {
				"backlog": 1024,
				"nodelay": True,
				"reuse-addr": True,
				"reuse-port": True,
			},
		},
		"cluster": {
			"node-id": server.cluster_node_id,
		},
		"config": {
			"local-keys": _get_local_keys(bool(server.outbound_only)),
		},
		"directory": {
			f"{cluster.storage_directory}": {
				"type": "internal",
				"store": f"{cluster.storage_directory}",
				"cache": {
					"size": 1048576,
					"ttl": {
						"negative": "10m",
						"positive": "1h",
					},
				},
			}
		},
		"storage": {
			"directory": cluster.storage_directory,
			"data": cluster.storage_data,
			"blob": cluster.storage_blob,
			"fts": cluster.storage_fts,
			"full-text": {"default-language": cluster.storage_full_text_default_language},
			"lookup": cluster.storage_lookup,
		},
		"account": {"purge": {"frequency": cluster.account_purge_frequency}},
		"email": {
			"encryption": {
				"enable": bool(cluster.email_encryption_enable),
				"append": bool(cluster.email_encryption_append),
			},
			"auto-expunge": _format_value_or_zero(cluster.email_auto_expunge, "d"),
		},
		"changes": {"max-history": cluster.changes_max_history},
		"jmap": {
			"email": {
				"max-attachment-size": cluster.jmap_email_max_attachment_size,
				"max-size": cluster.jmap_email_max_size,
				"parse": {"max-items": cluster.jmap_email_parse_max_items},
			},
			"protocol": {
				"changes": {
					"max-results": cluster.jmap_protocol_changes_max_results,
				},
				"request": {
					"max-concurrent": cluster.jmap_protocol_request_max_concurrent,
					"max-size": cluster.jmap_protocol_request_max_size,
					"max-calls": cluster.jmap_protocol_request_max_calls,
				},
				"get": {"max-objects": cluster.jmap_protocol_get_max_objects},
				"set": {"max-objects": cluster.jmap_protocol_set_max_objects},
				"query": {"max-results": cluster.jmap_protocol_query_max_results},
				"upload": {
					"max-size": cluster.jmap_protocol_upload_max_size,
					"max-concurrent": cluster.jmap_protocol_upload_max_concurrent,
					"ttl": _format_value_or_zero(cluster.jmap_protocol_upload_ttl, "h"),
					"quota": {
						"files": cluster.jmap_protocol_upload_quota_files,
						"size": cluster.jmap_protocol_upload_quota_size,
					},
				},
			},
			"mailbox": {
				"max-depth": cluster.jmap_mailbox_max_depth,
				"max-name-length": cluster.jmap_mailbox_max_name_length,
			},
			"push": {
				"max-total": cluster.jmap_push_max_total,
				"throttle": _format_value_or_zero(cluster.jmap_push_throttle, "ms"),
				"attempts": {
					"interval": _format_value_or_zero(cluster.jmap_push_attempts_interval, "ms"),
					"max": cluster.jmap_push_attempts_max,
				},
				"retry": {
					"interval": _format_value_or_zero(cluster.jmap_push_retry_interval, "ms"),
				},
				"timeout": {
					"request": _format_value_or_zero(cluster.jmap_push_timeout_request, "ms"),
					"verify": _format_value_or_zero(cluster.jmap_push_timeout_verify, "ms"),
				},
			},
		},
		"store": _get_stores(cluster.stores),
		"metrics": {
			"open-telemetry": {
				"transport": cluster.metrics_open_telemetry_transport.lower(),
				"endpoint": cluster.metrics_open_telemetry_endpoint,
				"timeout": _format_value_or_zero(cluster.metrics_open_telemetry_timeout, "s"),
				"interval": _format_value_or_zero(cluster.metrics_open_telemetry_interval, "s"),
			},
			"prometheus": {
				"enable": bool(cluster.metrics_prometheus_enable),
				"auth": {
					"username": cluster.metrics_prometheus_auth_username,
					"secret": password_or_none(cluster, "metrics_prometheus_auth_secret"),
				},
			},
		},
		"tracer": _get_traces(cluster.traces),
	}

	if server.outbound_only:
		config.setdefault("session", {}).setdefault("rcpt", {})["directory"] = False
		config.setdefault("queue", {}).setdefault("strategy", {})["route"] = "'mx'"

	toml_lines = []
	for key, value in sorted(flatten_dict(config).items()):
		if value or isinstance(value, bool):
			if isinstance(value, str):
				if (value.startswith("[") and "{ if = " in value and "}" in value) or (
					key.startswith("certificate.") and value.startswith("'''") and value.endswith("'''")
				):
					formatted_value = value
				else:
					formatted_value = f'"{value}"'
			elif isinstance(value, bool):
				formatted_value = str(value).lower()
			elif isinstance(value, list):
				formatted_list = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in value)
				formatted_value = f"[{formatted_list}]"
			else:
				formatted_value = str(value)

			toml_lines.append(f"{key} = {formatted_value}")

	return "\n".join(toml_lines) + "\n"
