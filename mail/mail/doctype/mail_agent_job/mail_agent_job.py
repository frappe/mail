# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
import requests
from frappe import _
from typing import TYPE_CHECKING
from frappe.model.document import Document
from frappe.utils import now, time_diff_in_seconds
from frappe.utils.password import get_decrypted_password

if TYPE_CHECKING:
	from requests import Response


class MailAgentJob(Document):
	def validate(self) -> None:
		self.validate_job_type()
		self.validate_request_data()

	def after_insert(self) -> None:
		self.enqueue_job()

	def validate_job_type(self) -> None:
		if not frappe.db.get_value("Mail Agent Job Type", self.job_type, "enabled"):
			frappe.throw(_("Job Type {0} is disabled.".format(frappe.bold(self.job_type))))

	def validate_request_data(self) -> None:
		if not self.request_data:
			self.request_data = "{}"

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify_update: bool = False,
		**kwargs
	) -> None:
		self.db_set(kwargs, update_modified=update_modified, commit=commit)

		if notify_update:
			self.notify_update()

	def enqueue_job(self) -> None:
		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"run",
			timeout=600,
			enqueue_after_commit=True,
		)

	def run(self) -> None:
		try:
			self.execute_on_start_method()
			started_at = now()
			self._db_set(status="Running", started_at=started_at, commit=True)

			agent = MailAgent(self.server)
			data = json.loads(self.request_data)
			response = agent.request(
				self.request_method,
				self.request_path,
				data=data,
			)

			if response.status_code == 200:
				response_data = json.dumps(response.json())
				self._db_set(status="Completed", response_data=response_data)
			else:
				raise Exception(response.text)

		except Exception:
			error_log = frappe.get_traceback(with_context=False)
			self._db_set(status="Failed", error_log=error_log)

		ended_at = now()
		self._db_set(
			ended_at=ended_at, duration=time_diff_in_seconds(ended_at, started_at), commit=True
		)
		self.execute_on_end_method()

	def execute_on_start_method(self) -> None:
		if self.execute_on_start:
			method = frappe.get_attr(self.execute_on_start)
			method(self)

	def execute_on_end_method(self) -> None:
		if self.execute_on_end:
			method = frappe.get_attr(self.execute_on_end)
			method(self)


class MailAgent:
	def __init__(self, server: str) -> None:
		self.server = server
		self.host, self.port = frappe.db.get_value(
			"Mail Server", server, ["host", "agent_port"]
		)

	def request(self, method, path, data=None) -> "Response":
		url = f"http://{self.host or self.server}:{self.port}/mail-agent/{path}"
		password = get_decrypted_password("Mail Server", self.server, "agent_password")
		headers = {"Authorization": f"bearer {password}"}
		response = requests.request(method, url, headers=headers, json=data, timeout=(10, 30))

		return response


def create_agent_job(
	server: str, job_type: str, request_data: str | list | dict = None
) -> "MailAgentJob":
	agent_job = frappe.new_doc("Mail Agent Job")
	agent_job.server = server
	agent_job.job_type = job_type
	agent_job.request_data = frappe.as_json({"data": request_data})
	agent_job.insert()

	return agent_job
