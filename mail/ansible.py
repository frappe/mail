import json
import os
import tempfile
from typing import TYPE_CHECKING, Any

import ansible_runner
import frappe
import yaml
from frappe import _
from frappe.utils import now, time_diff_in_seconds

from mail.utils import reconnect_on_failure

if TYPE_CHECKING:
	from mail.server.doctype.server_ansible_play.server_ansible_play import ServerAnsiblePlay


class Ansible:
	"""Ansible class to run playbooks and track their progress."""

	def __init__(
		self,
		server: str,
		playbook: str,
		variables: dict[str | Any] | None = None,
	) -> None:
		self.server = server
		self.playbook = playbook
		self.variables = variables or {}
		self._create_play_record()

	@classmethod
	def from_play(cls, play_name: str) -> "Ansible":
		"""Create an Ansible instance from an existing Server Ansible Play record."""

		play = frappe.get_doc("Server Ansible Play", play_name)

		self = cls.__new__(cls)
		self.play = play.name
		self.server = play.server
		self.playbook = play.playbook

		self.variables = {}
		for variable in play.variables:
			try:
				self.variables[variable.key_] = json.loads(variable.value)
			except (TypeError, json.JSONDecodeError):
				self.variables[variable.key_] = variable.value

		self.tasks = {}
		if tasks := frappe.db.get_all(
			"Ansible Play Task",
			filters={"play": self.play},
			fields=["task", "name"],
			order_by="creation asc",
			as_list=True,
		):
			self.tasks = frappe._dict(tasks)

		return self

	@property
	def playbook_path(self) -> str:
		"""Returns the absolute path to the playbook."""

		return os.path.join(frappe.get_app_path("mail", "utils", "ansible", "playbooks"), self.playbook)

	def _create_play_record(self) -> None:
		"""Creates a Server Ansible Play record and associated Ansible Play Task records."""

		if hasattr(self, "play") and self.play:
			return

		play = self._get_play()

		play = frappe.new_doc("Server Ansible Play")
		play.server = self.server
		play.play = play["name"]
		play.playbook = self.playbook

		for key, value in self.variables.items():
			if isinstance(value, int | bool):
				value = str(value)
			elif isinstance(value, list | dict):
				value = json.dumps(value, indent=4)
			elif not isinstance(value, str):
				frappe.throw(_("Variable value cannot be of type {0}").format(type(value)))

			play.append("variables", {"key_": key, "value": value})

		play.insert(ignore_permissions=True)
		self.play = play.name

		self._create_task_records(play=play)

	def _create_task_records(self, play: dict | None = None) -> None:
		"""Creates Ansible Play Task records for each task in the play."""

		if not hasattr(self, "play") or not self.play:
			frappe.throw(_("Play record must be created before creating task records."))
		elif hasattr(self, "tasks") and self.tasks:
			return

		play = play or self._get_play()

		self.tasks = {}
		for task in play["tasks"]:
			tdoc = frappe.new_doc("Ansible Play Task")
			tdoc.play = self.play
			tdoc.task = task["name"]
			tdoc.insert(ignore_permissions=True)
			self.tasks[tdoc.task] = tdoc.name

	def _get_play(self) -> dict:
		"""Returns the first play from the playbook."""

		if not os.path.exists(self.playbook_path):
			frappe.throw(_("Playbook {0} does not exist").format(self.playbook))

		with open(self.playbook_path) as f:
			try:
				plays = yaml.safe_load(f)
			except yaml.YAMLError as e:
				frappe.throw(_("Error parsing playbook {0}: {1}").format(self.playbook, str(e)))

		return plays[0]

	def run(self, quiet: bool = True) -> "ServerAnsiblePlay":
		"""Run the playbook using ansible-runner and track its progress."""

		server = frappe.get_doc("Mail Server", self.server)
		cluster = frappe.get_doc("Mail Cluster", server.cluster)

		private_key_file = tempfile.NamedTemporaryFile(delete=False)
		private_key_file.write(cluster.get_password("ssh_private_key").encode())
		private_key_file.close()

		inventory = (
			f"{server.hostname} "
			f"ansible_user={server.ssh_user} "
			f"ansible_port={server.ssh_port} "
			f"ansible_ssh_private_key_file={private_key_file.name}"
		)

		ansible_runner.run(
			playbook=self.playbook_path,
			inventory=inventory,
			extravars=self.variables,
			event_handler=self.event_handler,
			quiet=quiet,
		)

		os.remove(private_key_file.name)

		return frappe.get_doc("Server Ansible Play", self.play)

	def event_handler(self, event: dict) -> None:
		"""Handle events from ansible-runner and update the play and task records accordingly."""

		if event_type := event.get("event"):
			if hasattr(self, event_type):
				method = getattr(self, event_type)
				if callable(method):
					method(event.get("event_data"))

	def playbook_on_start(self, event_data: dict) -> None:
		"""Called when the playbook starts."""

		self.update_play(status="Running")

	def playbook_on_task_start(self, event_data: dict) -> None:
		"""Called when a task starts."""

		self.update_task(status="Running", task=event_data)

	def runner_on_ok(self, event_data: dict) -> None:
		"""Called when a task completes successfully."""

		self.update_task(status="Success", result=event_data)

	def runner_on_failed(self, event_data: dict) -> None:
		"""Called when a task fails."""

		self.update_task(status="Failed", result=event_data)

	def runner_on_unreachable(self, event_data: dict) -> None:
		"""Called when a host is unreachable."""

		self.update_task(status="Unreachable", result=event_data)

	def runner_on_skipped(self, event_data: dict) -> None:
		"""Called when a task is skipped."""

		self.update_task(status="Skipped", result=event_data)

	def playbook_on_stats(self, event_data: dict) -> None:
		"""Called when the playbook finishes. Update the play record with final stats."""

		stats = {}
		for key in ["changed", "dark", "failures", "ignored", "ok", "processed", "rescued", "skipped"]:
			stats[key] = event_data.get(key, {}).get(self.server, 0)
		stats["unreachable"] = stats.pop("dark", 0)
		self.update_play(stats=stats)

	@reconnect_on_failure()
	def update_play(self, status: str | None = None, stats: dict | None = None) -> None:
		"""Updates the Server Ansible Play record with the given status and stats."""

		if not status and not stats:
			return

		play = frappe.get_doc("Server Ansible Play", self.play)

		if stats:
			ended_at = now()
			duration = time_diff_in_seconds(ended_at, play.started_at)
			status = "Failed" if stats["failures"] or stats["unreachable"] else "Success"
			kwargs = {**stats, "status": status, "ended_at": ended_at, "duration": duration}
			play._db_set(commit=True, notify=True, **kwargs)
		else:
			started_at = now()
			started_after = time_diff_in_seconds(started_at, play.creation)
			play._db_set(
				status=status, started_at=started_at, started_after=started_after, commit=True, notify=True
			)

	@reconnect_on_failure()
	def update_task(self, status: str, task: dict | None = None, result: dict | None = None) -> None:
		"""Updates the Ansible Play Task record with the given status, task, and result."""

		if not any([task, result]):
			return

		if task:
			name = task["task"]
			parsed = frappe._dict()
		else:
			name = result["task"]
			parsed = frappe._dict(result.get("res") or {})

		task_name = self.tasks.get(name)
		if not task_name:
			return

		tdoc = frappe.get_doc("Ansible Play Task", task_name)

		kwargs = {"status": status}
		if parsed:
			kwargs.update({"stdout": parsed.stdout, "stderr": parsed.stderr, "exception": parsed.msg})
			for key in ("stdout", "stdout_lines", "stderr", "stderr_lines", "msg"):
				result["res"].pop(key, None)

			kwargs["result"] = json.dumps(result, indent=4)

		if status == "Running":
			kwargs.update({"started_at": now()})
		elif status in ("Success", "Failed", "Unreachable", "Skipped"):
			ended_at = now()
			duration = time_diff_in_seconds(ended_at, tdoc.started_at)
			kwargs.update({"ended_at": ended_at, "duration": duration})

		tdoc._db_set(commit=True, notify=True, **kwargs)
		self._publish_play_progress(tdoc.name)

	def _publish_play_progress(self, task: str) -> None:
		"""Publish the play progress to the user via real-time updates."""

		task_list = list(self.tasks.values())
		frappe.publish_realtime(
			"ansible_play_progress",
			{"progress": task_list.index(task), "total": len(task_list), "play": self.play},
			doctype="Server Ansible Play",
			docname=self.play,
			user=frappe.session.user,
		)
