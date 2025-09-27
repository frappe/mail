# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import os
import subprocess
import tempfile

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils import cint, now, time_diff_in_seconds
from uuid_utils import uuid7

from mail.utils import get_mail_app_path


class MailServerPlaybook(Document):
	@property
	def started_after(self) -> float:
		"""Returns the time taken to start the playbook in seconds."""

		if self.started_at and self.creation:
			started_after = time_diff_in_seconds(self.started_at, self.creation)
			if started_after > 0:
				return started_after

		return 0.0

	@property
	def duration(self) -> float:
		"""Returns the duration of the playbook in seconds."""

		if self.started_at and self.ended_at:
			duration = time_diff_in_seconds(self.ended_at, self.started_at)
			if duration > 0:
				return duration

		return 0.0

	@property
	def playbook_path(self) -> str:
		"""Returns the absolute path of the playbook."""

		return os.path.join(get_mail_app_path(), "mail/utils/ansible/playbooks", self.playbook)

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_status()
		self.validate_server()
		self.validate_playbook()

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

	def validate_playbook(self) -> None:
		"""Validate if the playbook path is valid."""

		if not self.playbook:
			frappe.throw(_("Playbook is required"))
		elif not os.path.isfile(self.playbook_path):
			frappe.throw(_("Playbook {0} does not exist.").format(self.playbook))

	def execute(self) -> None:
		"""Executes the Ansible playbook."""

		kwargs = {}
		self._db_set(status="Running", started_at=now(), error_log=None, commit=True, notify=True)

		try:
			self.validate_server()

			server = frappe.get_doc("Mail Server", self.server)
			cluster = frappe.get_doc("Mail Cluster", server.cluster)

			private_key_file = tempfile.NamedTemporaryFile(delete=False)
			private_key_file.write(cluster.get_password("ssh_private_key").encode())
			private_key_file.close()

			inventory = f"""
			[mailserver]
			{server.hostname} ansible_port={server.ssh_port} ansible_user={server.ssh_user}
			"""
			inventory_file = tempfile.NamedTemporaryFile(delete=False, mode="w")
			inventory_file.write(inventory)
			inventory_file.close()

			cmd = [
				"ansible-playbook",
				"-i",
				inventory_file.name,
				self.playbook_path,
				"--private-key",
				private_key_file.name,
			]

			if json.loads(self.playbook_kwargs or "{}"):
				cmd.extend(["--extra-vars", self.playbook_kwargs])

			process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			stdout, stderr = process.communicate()

			os.remove(private_key_file.name)
			os.remove(inventory_file.name)

			kwargs.update(
				{
					"status": "Success" if process.returncode == 0 else "Failed",
					"exit_code": process.returncode,
					"stdout": stdout.decode(),
					"stderr": stderr.decode(),
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

		self._db_set(notify=True, ended_at=now(), **kwargs)

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retries a failed playbook."""

		frappe.only_for("System Manager")

		if self.status != "Failed":
			frappe.throw(_("Only failed playbooks can be retried."))

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


def retry_failed_playbooks() -> None:
	"""Called by the scheduler to retry failed playbooks."""

	PB = frappe.qb.DocType("Mail Server Playbook")
	playbooks = (
		frappe.qb.from_(PB)
		.select(PB.name)
		.where((PB.status == "Failed") & (PB.retries > 0) & (PB.retries < PB.max_retries))
		.orderby(PB.creation, order=Order.asc)
	).run(pluck="name")

	if not playbooks:
		return

	for playbook in playbooks:
		doc = frappe.get_doc("Mail Server Playbook", playbook)
		doc.retry()
