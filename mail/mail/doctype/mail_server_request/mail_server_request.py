# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from collections.abc import Callable
from urllib.parse import quote

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, time_diff_in_seconds
from uuid_utils import uuid7

from mail.utils import get_dotted_path


class MailServerRequest(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_cluster()
		self.validate_endpoint()

	def after_insert(self) -> None:
		if frappe.flags.do_not_enqueue:
			self.execute()
		else:
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"execute",
				enqueue_after_commit=True,
			)

	def validate_cluster(self) -> None:
		"""Validate if the cluster is enabled."""

		if not self.cluster:
			frappe.throw(_("Mail Cluster is required."))

		if not frappe.get_cached_value("Mail Cluster", self.cluster, "enabled"):
			frappe.throw(_("Mail Cluster {0} is disabled.").format(self.cluster))

	def validate_endpoint(self) -> None:
		"""Validates the endpoint."""

		self.endpoint = quote(self.endpoint)

	def execute(self) -> None:
		"""Executes the job."""

		started_at = now()
		self._db_set(status="Running", started_at=started_at, commit=True)

		kwargs = {}
		try:
			self._execute_method_on_start()
			self._execute_request()
			self._execute_method_on_end()
			kwargs["status"] = "Completed"
		except Exception:
			error_log = frappe.get_traceback(with_context=True)
			kwargs["error_log"] = error_log
			kwargs["status"] = "Failed"
		finally:
			kwargs["ended_at"] = now()
			kwargs["duration"] = time_diff_in_seconds(kwargs["ended_at"], started_at)
			self._db_set(**kwargs, commit=True)

	def _execute_method_on_start(self) -> None:
		"""Executes the method on start."""

		if self.execute_on_start:
			method = frappe.get_attr(self.execute_on_start)
			method(self)

	def _execute_request(self) -> None:
		"""Executes the request."""

		cluster = frappe.get_cached_doc("Mail Cluster", self.cluster)

		if not cluster.enabled:
			frappe.throw(_("Mail Cluster {0} is disabled.").format(self.cluster))

		from mail.mail_server import MailServerAPI

		api_key = cluster.get_password("api_key") if cluster.api_key else None
		server_api = MailServerAPI(
			cluster.base_url,
			api_key=api_key,
			username=cluster.fallback_admin_user,
			password=cluster.get_password("fallback_admin_password"),
		)
		response = server_api.request(
			method=self.method,
			endpoint=self.endpoint,
			params=self.request_params,
			data=self.request_data,
			json=self.request_json,
			headers=self.request_headers,
		)

		response_json = json.dumps(response.json())
		if response.status_code == 200:
			self._db_set(response_json=response_json)
		else:
			frappe.throw(title=_("Mail Server Request Failed"), msg=response_json)

	def _execute_method_on_end(self) -> None:
		"""Executes the method on end."""

		if self.execute_on_end:
			method = frappe.get_attr(self.execute_on_end)
			method(self)

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify_update: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, commit=commit)

		if notify_update:
			self.notify_update()


def create_mail_server_request(
	cluster: str,
	method: str,
	endpoint: str,
	request_headers: dict | None = None,
	request_params: dict | None = None,
	request_data: str | None = None,
	request_json: dict | None = None,
	execute_on_start: Callable | str | None = None,
	execute_on_end: Callable | str | None = None,
	do_not_enqueue: bool = False,
) -> "MailServerRequest":
	"""Creates a new Mail Server Request."""

	if do_not_enqueue:
		frappe.flags.do_not_enqueue = True

	request = frappe.new_doc("Mail Server Request")
	request.cluster = cluster
	request.method = method
	request.endpoint = endpoint
	request.request_headers = request_headers
	request.request_params = request_params
	request.request_data = request_data
	request.request_json = request_json
	request.execute_on_start = (
		get_dotted_path(execute_on_start) if callable(execute_on_start) else execute_on_start
	)
	request.execute_on_end = get_dotted_path(execute_on_end) if callable(execute_on_end) else execute_on_end
	request.insert(ignore_permissions=True)

	return request
