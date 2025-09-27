# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import io
import json
import time

import frappe
import paramiko
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now, time_diff_in_seconds
from uuid_utils import uuid7


class MailServerJob(Document):
	@property
	def started_after(self) -> float:
		"""Returns the time taken to start the job in seconds."""

		if self.started_at and self.creation:
			started_after = time_diff_in_seconds(self.started_at, self.creation)
			if started_after > 0:
				return started_after

		return 0.0

	@property
	def duration(self) -> float:
		"""Returns the duration of the job in seconds."""

		if self.started_at and self.ended_at:
			duration = time_diff_in_seconds(self.ended_at, self.started_at)
			if duration > 0:
				return duration

		return 0.0

	@property
	def commands(self) -> str | None:
		"""Returns the commands as a pretty-printed JSON string."""

		_commands = json.loads(self._commands or "[]")
		return json.dumps(_commands, indent=4) if _commands else None

	@property
	def results(self) -> str | None:
		"""Returns the results as a pretty-printed JSON string."""

		_results = json.loads(self._results or "{}")
		return json.dumps(_results, indent=4) if _results else None

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_status()
		self.validate_server()
		self.validate_commands()

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

	def validate_commands(self) -> None:
		"""Validate if _commands are set."""

		_commands = json.loads(self._commands or "[]")

		if not _commands:
			frappe.throw(_("Please add at least one command to execute."))
		else:
			self._commands = json.dumps(_commands)

	def execute(self) -> None:
		"""Executes the commands on the Mail Server via SSH."""

		kwargs = {}
		self._db_set(status="Running", started_at=now(), error_log=None, commit=True, notify=True)

		try:
			self.validate_server()

			server = frappe.get_doc("Mail Server", self.server)
			cluster = frappe.get_doc("Mail Cluster", server.cluster)
			key = paramiko.RSAKey.from_private_key(io.StringIO(cluster.get_password("ssh_private_key")))

			client = paramiko.SSHClient()
			client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			client.connect(
				hostname=server.hostname, port=server.ssh_port, username=server.ssh_user, pkey=key, timeout=30
			)

			_results = {}
			for cmd in json.loads(self._commands):
				cmd_start = time.time()
				_stdin, stdout, stderr = client.exec_command(cmd)
				exit_status = stdout.channel.recv_exit_status()
				cmd_end = time.time()

				_results[cmd] = {
					"stdout": stdout.read().decode(),
					"stderr": stderr.read().decode(),
					"exit_code": exit_status,
					"duration": round(cmd_end - cmd_start, 2),
				}

			client.close()
			kwargs.update(
				{
					"status": "Success" if all(r["exit_code"] == 0 for r in _results.values()) else "Failed",
					"_results": json.dumps(_results, indent=4),
				}
			)

			if kwargs["status"] == "Failed":
				kwargs["failed_count"] = cint(self.failed_count) + 1

		except Exception:
			failed_count = cint(self.failed_count) + 1
			kwargs.update(
				{
					"status": "Failed",
					"failed_count": failed_count,
					"error_log": frappe.get_traceback(with_context=True),
				}
			)

		self._db_set(notify=True, ended_at=now(), **kwargs)

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retries a failed job."""

		frappe.only_for("System Manager")

		if self.status != "Failed":
			frappe.throw(_("Only failed jobs can be retried."))

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
