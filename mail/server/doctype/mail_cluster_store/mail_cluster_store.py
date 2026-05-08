# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

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
					"timeout": cint(self.timeout),
					"useTls": cint(self.use_tls),
					"allowInvalidCerts": cint(self.allow_invalid_certs),
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
					"timeout": cint(self.timeout),
					"useTls": cint(self.use_tls),
					"allowInvalidCerts": cint(self.allow_invalid_certs),
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

		return config

	def validate(self) -> None:
		"""Validates the cluster store configuration."""

		if not self.description:
			self.description = self.type
