# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from typing import Optional
from frappe.query_builder import Interval
from frappe.model.document import Document
from frappe.query_builder.functions import Now
from frappe.utils import now, time_diff_in_seconds


class MailAgentJob(Document):
	@staticmethod
	def clear_old_logs(days=14):
		table = frappe.qb.DocType("Mail Agent Job")
		frappe.db.delete(
			table,
			filters=((table.modified < (Now() - Interval(days=days))))
			& (table.status == "Completed"),
		)

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
		**kwargs,
	) -> None:
		self.db_set(kwargs, update_modified=update_modified, commit=commit)

		if notify_update:
			self.notify_update()

	def enqueue_job(self) -> None:
		queue = self.queue or "default"
		timeout = self.timeout or None

		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"run",
			queue=queue,
			timeout=timeout,
			enqueue_after_commit=True,
		)

	def run(self) -> None:
		started_at = now()
		self._db_set(status="Running", started_at=started_at, commit=True)

		try:
			self.execute_on_start_method()
		except Exception:
			error_log = frappe.get_traceback(with_context=False)
			self._db_set(on_start_error_log=error_log)

		try:
			agent = frappe.get_cached_doc("Mail Agent", self.agent)
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

		try:
			self.execute_on_end_method()
		except Exception:
			error_log = frappe.get_traceback(with_context=False)
			self._db_set(on_end_error_log=error_log)

		ended_at = now()
		self._db_set(
			ended_at=ended_at,
			duration=time_diff_in_seconds(ended_at, started_at),
			commit=True,
			notify_update=True,
		)

	def execute_on_start_method(self) -> None:
		if self.execute_on_start:
			method = frappe.get_attr(self.execute_on_start)
			method(self)

	def execute_on_end_method(self) -> None:
		if self.execute_on_end:
			method = frappe.get_attr(self.execute_on_end)
			method(self)

	@frappe.whitelist()
	def rerun(self) -> None:
		self._db_set(status="Queued", error_log=None)
		self.enqueue_job()


def create_agent_job(
	agent: str, job_type: str, request_data: Optional[dict] = None
) -> "MailAgentJob":
	agent_job = frappe.new_doc("Mail Agent Job")
	agent_job.agent = agent
	agent_job.job_type = job_type
	agent_job.request_data = json.dumps(request_data or {})
	agent_job.insert()

	return agent_job
