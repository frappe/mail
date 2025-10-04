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


class MailServerAnsiblePlay(Document):
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
		elif not os.path.isfile(self._get_playbook_path()):
			frappe.throw(_("Playbook {0} does not exist.").format(self.playbook))

	def execute(self) -> None:
		"""Executes the Ansible playbook."""

		kwargs = {}
		started_at = now()
		self._db_set(
			status="Running",
			started_at=started_at,
			started_after=time_diff_in_seconds(started_at, self.creation),
			error_log=None,
			commit=True,
			notify=True,
		)

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
				self._get_playbook_path(),
				"--private-key",
				private_key_file.name,
			]

			if self.variables:
				extra_vars = {}
				for variable in self.variables:
					try:
						extra_vars[variable.key_] = json.loads(variable.value)
					except (TypeError, json.JSONDecodeError):
						extra_vars[variable.key_] = variable.value

				cmd.extend(["--extra-vars", json.dumps(extra_vars)])

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

		ended_at = now()
		self._db_set(
			ended_at=ended_at, duration=time_diff_in_seconds(ended_at, started_at), notify=True, **kwargs
		)

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retries a failed ansible play."""

		frappe.only_for("System Manager")

		if self.status != "Failed":
			frappe.throw(_("Only failed ansible plays can be retried."))

		self._db_set(status="Pending", notify=True)

		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"execute",
			queue="long",
			enqueue_after_commit=True,
		)

	def _get_playbook_path(self) -> str:
		"""Returns the absolute path of the playbook."""

		return os.path.join(frappe.get_app_path("mail", "utils", "ansible", "playbooks"), self.playbook)

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


def retry_failed_ansible_plays() -> None:
	"""Called by the scheduler to retry failed ansible plays."""

	PB = frappe.qb.DocType("")
	plays = (
		frappe.qb.from_(PB)
		.select(PB.name)
		.where((PB.status == "Failed") & (PB.retries > 0) & (PB.retries < PB.max_retries))
		.orderby(PB.creation, order=Order.asc)
	).run(pluck="name")

	if not plays:
		return

	for play in plays:
		doc = frappe.get_doc("Mail Server Ansible Play", play)
		doc.retry()
