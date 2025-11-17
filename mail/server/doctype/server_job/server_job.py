# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import io

import frappe
import paramiko
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils import cint, now, time_diff_in_seconds
from uuid_utils import uuid7


class ServerJob(Document):
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
				timeout=cint(frappe.conf.server_job_timeout) or 1500,
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
		"""Validates that at least one command is provided."""

		if not self.commands:
			frappe.throw(_("Please add at least one command to execute."))

	def execute(self) -> None:
		"""Executes the commands on the Mail Server via SSH."""

		started_at = now()
		self._db_set(
			status="Running",
			started_at=started_at,
			ended_at=None,
			started_after=time_diff_in_seconds(started_at, self.creation),
			duration=0,
			success=0,
			failed=0,
			error_log=None,
			commit=True,
			notify=True,
		)
		frappe.db.set_value(
			"Server Job Command",
			{"parenttype": self.doctype, "parent": self.name},
			{
				"status": "Pending",
				"started_at": None,
				"ended_at": None,
				"duration": 0,
				"exit_code": 0,
				"stdout": None,
				"stderr": None,
			},
		)

		kwargs = {}
		success_count = 0
		failed_count = 0
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

			for command in self.commands:
				cmd_started_at = now()
				command._db_set(status="Running", started_at=cmd_started_at, commit=True)

				_stdin, stdout, stderr = client.exec_command(command.command)
				exit_code = stdout.channel.recv_exit_status()

				cmd_ended_at = now()
				command._db_set(
					status="Success" if exit_code == 0 else "Failed",
					ended_at=cmd_ended_at,
					exit_code=exit_code,
					stdout=stdout.read().decode(),
					stderr=stderr.read().decode(),
					duration=time_diff_in_seconds(cmd_ended_at, cmd_started_at),
					commit=True,
				)

				if exit_code == 0:
					success_count += 1
				elif not command.ignore_errors:
					failed_count += 1
					frappe.throw(
						_("Command '{0}' failed with exit code {1}").format(
							f"{command.command[:20]} ...", exit_code
						)
					)

			client.close()
			kwargs["status"] = "Success"

		except Exception:
			kwargs.update(
				{
					"status": "Failed",
					"retries": cint(self.retries) + 1,
					"error_log": frappe.get_traceback(with_context=True),
				}
			)

		ended_at = now()
		self._db_set(
			ended_at=ended_at,
			duration=time_diff_in_seconds(ended_at, started_at),
			success=success_count,
			failed=failed_count,
			notify=True,
			**kwargs,
		)

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
			timeout=cint(frappe.conf.server_job_timeout) or 1500,
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


def retry_failed_jobs() -> None:
	"""Called by the scheduler to retry failed jobs."""

	JOB = frappe.qb.DocType("Server Job")
	jobs = (
		frappe.qb.from_(JOB)
		.select(JOB.name)
		.where((JOB.status == "Failed") & (JOB.retries > 0) & (JOB.retries < JOB.max_retries))
		.orderby(JOB.creation, order=Order.asc)
	).run(pluck="name")

	if not jobs:
		return

	for job in jobs:
		doc = frappe.get_doc("Server Job", job)
		doc.retry()
