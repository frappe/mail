# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import os
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils import cint, now, time_diff_in_seconds

from mail.ansible import Ansible
from mail.utils import get_config


class ServerAnsiblePlay(Document):
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
				timeout=cint(get_config("ansible_play_timeout")),
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

		if self.status == "Running":
			frappe.throw(_("Ansible play is already running."))

		try:
			self.validate_server()
			ansible = Ansible.from_play(self.name)
			ansible._create_task_records()
			ansible.run()

			self.reload()
			if self.status == "Failed":
				self._db_set(retries=cint(self.retries) + 1, notify=True)

		except Exception:
			error_log = frappe.get_traceback(with_context=True)
			kwargs = {
				"status": "Failed",
				"retries": cint(self.retries) + 1,
				"error_log": error_log,
			}

			if self.started_at:
				ended_at = now()
				kwargs.update(
					{
						"ended_at": ended_at,
						"duration": time_diff_in_seconds(ended_at, self.started_at),
					}
				)

			self._db_set(notify=True, **kwargs)
			self._mark_pending_tasks_as_failed(error_log)

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retries a failed ansible play."""

		frappe.only_for("System Manager")

		if self.status != "Failed":
			frappe.throw(_("Only failed ansible plays can be retried."))

		kwargs = {
			"status": "Pending",
			"started_at": None,
			"started_after": 0,
			"ended_at": None,
			"duration": 0,
			"ok": 0,
			"changed": 0,
			"failures": 0,
			"unreachable": 0,
			"skipped": 0,
			"rescued": 0,
			"ignored": 0,
			"processed": 0,
			"error_log": None,
		}
		self._db_set(notify=True, **kwargs)

		frappe.db.set_value(
			"Server Ansible Play Task",
			{"play": self.name},
			{
				"status": "Pending",
				"started_at": None,
				"ended_at": None,
				"duration": 0,
				"stdout": None,
				"stderr": None,
				"exception": None,
				"result": None,
			},
		)

		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"execute",
			queue="long",
			timeout=cint(get_config("ansible_play_timeout")),
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

	def _mark_pending_tasks_as_failed(self, error_log: str) -> None:
		"""Marks unresolved task rows as failed when play-level execution aborts."""

		for task in frappe.get_all(
			"Server Ansible Play Task",
			filters={"play": self.name, "status": ["in", ["Pending", "Running"]]},
			fields=["name", "started_at"],
		):
			ended_at = now()
			started_at = task.started_at or ended_at
			frappe.db.set_value(
				"Server Ansible Play Task",
				task.name,
				{
					"status": "Failed",
					"started_at": started_at,
					"ended_at": ended_at,
					"duration": time_diff_in_seconds(ended_at, started_at),
					"exception": error_log,
				},
				update_modified=True,
			)


def retry_failed_ansible_plays() -> None:
	"""Called by the scheduler to retry failed ansible plays."""

	PLAY = frappe.qb.DocType("Server Ansible Play")
	plays = (
		frappe.qb.from_(PLAY)
		.select(PLAY.name)
		.where((PLAY.status == "Failed") & (PLAY.retries > 0) & (PLAY.retries < PLAY.max_retries))
		.orderby(PLAY.creation, order=Order.asc)
	).run(pluck="name")

	if not plays:
		return

	for play in plays:
		doc = frappe.get_doc("Server Ansible Play", play)
		doc.retry()
