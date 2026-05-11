# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class MailClusterStore(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	@property
	def config(self) -> dict:
		"""Returns the configuration for the cluster store."""

		if not self.type:
			return {}

		config = {"@type": self.type}

		if self.type == "RocksDb":
			config.update(
				{
					"path": self.path,
					"blobSize": cint(self.blob_size),
					"bufferSize": cint(self.buffer_size),
					"poolWorkers": cint(self.pool_workers),
				}
			)

		elif self.type == "Sqlite":
			config.update(
				{
					"path": self.path,
					"poolWorkers": cint(self.pool_workers),
					"poolMaxConnections": cint(self.pool_max_connections),
				}
			)

		elif self.type == "FoundationDb":
			config.update(
				{
					"clusterFile": self.cluster_file,
					"datacenterId": self.datacenter_id,
					"machineId": self.machine_id,
					"transactionRetryDelay": cint(self.transaction_retry_delay),
					"transactionRetryLimit": cint(self.transaction_retry_limit),
					"transactionTimeout": cint(self.transaction_timeout),
				}
			)

		elif self.type == "PostgreSql":
			config.update(
				{
					"timeout": self.timeout,
					"useTls": bool(self.use_tls),
					"allowInvalidCerts": bool(self.allow_invalid_certs),
					"poolMaxConnections": cint(self.pool_max_connections),
					"poolRecyclingMethod": self.pool_recycling_method,
					"host": self.host,
					"port": cint(self.port),
					"database": self.database,
					"authUsername": self.auth_username,
					"authSecret": self.get_password("auth_secret") if self.auth_secret else None,
					"options": self.options,
				}
			)

		elif self.type == "MySql":
			config.update(
				{
					"timeout": self.timeout,
					"useTls": bool(self.use_tls),
					"allowInvalidCerts": bool(self.allow_invalid_certs),
					"maxAllowedPacket": cint(self.max_allowed_packet),
					"poolMaxConnections": cint(self.pool_max_connections),
					"poolMinConnections": cint(self.pool_min_connections),
					"host": self.host,
					"port": cint(self.port),
					"database": self.database,
					"authUsername": self.auth_username,
					"authSecret": self.get_password("auth_secret") if self.auth_secret else None,
				}
			)

		elif self.type == "S3":
			config.update(
				{
					"region": self.region,
					"bucket": self.bucket,
					"accessKey": self.access_key,
					"secretKey": self.get_password("secret_key") if self.secret_key else None,
					"securityToken": self.get_password("security_token") if self.security_token else None,
					"sessionToken": self.get_password("session_token") if self.session_token else None,
					"profile": self.profile,
					"timeout": self.timeout,
					"maxRetries": cint(self.max_retries),
					"keyPrefix": self.key_prefix,
					"allowInvalidCerts": bool(self.allow_invalid_certs),
					"verifyAfterWrite": bool(self.verify_after_write),
				}
			)

		elif self.type == "Azure":
			config.update(
				{
					"storageAccount": self.storage_account,
					"container": self.container,
					"accessKey": self.get_password("access_key") if self.access_key else None,
					"sasToken": self.get_password("sas_token") if self.sas_token else None,
					"timeout": self.timeout,
					"maxRetries": cint(self.max_retries),
					"keyPrefix": self.key_prefix,
				}
			)

		elif self.type == "FileSystem":
			config.update(
				{
					"path": self.path,
					"depth": cint(self.depth),
				}
			)

		elif self.type == "ElasticSearch":
			http_auth = frappe.get_doc("Mail Cluster Store HTTP Auth", self.http_auth)
			config.update(
				{
					"url": self.url,
					"numReplicas": cint(self.num_replicas),
					"numShards": cint(self.num_shards),
					"includeSource": bool(self.include_source),
					"timeout": cint(self.timeout),
					"allowInvalidCerts": bool(self.allow_invalid_certs),
					"httpAuth": http_auth.config,
					"httpHeaders": json.loads(self.http_headers) if self.http_headers else {},
				}
			)

		elif self.type == "Meilisearch":
			http_auth = frappe.get_doc("Mail Cluster Store HTTP Auth", self.http_auth)
			config.update(
				{
					"url": self.url,
					"pollInterval": self.pool_interval,
					"maxRetries": cint(self.max_retries),
					"failOnTimeout": bool(self.fail_on_timeout),
					"timeout": cint(self.timeout),
					"allowInvalidCerts": bool(self.allow_invalid_certs),
					"httpAuth": http_auth.config,
					"httpHeaders": json.loads(self.http_headers) if self.http_headers else {},
				}
			)

		elif self.type == "Redis":
			config.update(
				{
					"url": self.url,
					"timeout": cint(self.timeout),
					"poolMaxConnections": cint(self.pool_max_connections),
					"poolTimeoutCreate": self.pool_timeout_create,
					"poolTimeoutWait": self.pool_timeout_wait,
					"poolTimeoutRecycle": self.pool_timeout_recycle,
				}
			)

		elif self.type == "RedisCluster":
			config.update(
				{
					"urls": json.loads(self.urls) if self.urls else [],
					"timeout": cint(self.timeout),
					"authUsername": self.auth_username,
					"authSecret": self.get_password("auth_secret") if self.auth_secret else None,
					"maxRetryWait": self.max_retry_wait,
					"minRetryWait": self.min_retry_wait,
					"maxRetries": cint(self.max_retries),
					"readFromReplicas": bool(self.read_from_replicas),
					"protocolVersion": self.protocol_version,
					"poolMaxConnections": cint(self.pool_max_connections),
					"poolTimeoutCreate": self.pool_timeout_create,
					"poolTimeoutWait": self.pool_timeout_wait,
					"poolTimeoutRecycle": self.pool_timeout_recycle,
				}
			)

		return config

	def validate(self) -> None:
		if not self.description:
			self.description = self.type

		self.validate_singleton_default()

	def validate_singleton_default(self) -> None:
		"""Validates that only one Default store exists."""

		if self.type in ["Default"]:
			if frappe.db.exists("Mail Cluster Store", {"type": self.type, "name": ["!=", self.name]}):
				frappe.throw(_("Only one {0} store is allowed.").format(self.type))
