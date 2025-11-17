# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from collections.abc import Callable
from typing import Literal
from urllib.parse import quote

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, time_diff_in_seconds
from uuid_utils import uuid7

from mail.utils import get_dotted_path


class MailBackendRequest(Document):
	@property
	def response_json(self) -> str | None:
		"""Returns the indented JSON response."""

		return json.dumps(json.loads(self._response_json), indent=4) if self._response_json else None

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_backend()
		self.validate_endpoint()

	def after_insert(self) -> None:
		if frappe.flags.do_not_enqueue:
			self.execute()
		else:
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"execute",
				queue="short",
				enqueue_after_commit=True,
			)

	def validate_backend(self) -> None:
		"""Validate if the backend is enabled."""

		if not self.backend_type or not self.backend_name:
			frappe.throw(_("Backend Type and Backend Name are required."))

		if not frappe.db.get_value(self.backend_type, self.backend_name, "enabled"):
			frappe.throw(_("{0} {1} is disabled.").format(self.backend_type, self.backend_name))

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

		if self.on_start:
			method = frappe.get_attr(self.on_start)
			kwargs = json.loads(self.on_start_kwargs or "{}")
			method(**kwargs)

	def _execute_request(self) -> None:
		"""Executes the request."""

		cluster_name = self.backend_name
		if self.backend_type == "Mail Server":
			cluster_name = frappe.db.get_value("Mail Server", self.backend_name, "cluster")

			if not cluster_name:
				frappe.throw(_("Mail Server {0} does not have a cluster.").format(self.backend_name))

		cluster = frappe.get_cached_doc("Mail Cluster", cluster_name)

		base_url = cluster.base_url
		if self.backend_type == "Mail Server":
			base_url = frappe.db.get_value("Mail Server", self.backend_name, "base_url")

			if not base_url:
				frappe.throw(_("Mail Server {0} does not have a base URL.").format(self.backend_name))

		from mail.backend import get_mail_backend_api

		backend_api = get_mail_backend_api(self.backend_type, self.backend_name)
		response = backend_api.request(
			method=self.method,
			endpoint=self.endpoint,
			params=self.request_params,
			data=self.request_data,
			json=self.request_json,
			headers=self.request_headers,
		)

		_response_json = json.dumps(response.json())
		if response.status_code == 200:
			self._db_set(_response_json=_response_json)
		else:
			frappe.throw(title=_("Mail Backend Request Failed"), msg=_response_json)

	def _execute_method_on_end(self) -> None:
		"""Executes the method on end."""

		if self.on_end:
			method = frappe.get_attr(self.on_end)
			kwargs = json.loads(self.on_end_kwargs or "{}")
			method(**kwargs)

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


def create_mail_backend_request(
	backend_type: Literal["Mail Cluster", "Mail Server"],
	backend_name: str,
	method: str,
	endpoint: str,
	request_headers: dict | None = None,
	request_params: dict | None = None,
	request_data: str | None = None,
	request_json: dict | None = None,
	on_start: Callable | str | None = None,
	on_start_kwargs: dict | None = None,
	on_end: Callable | str | None = None,
	on_end_kwargs: dict | None = None,
	do_not_enqueue: bool = False,
) -> "MailBackendRequest":
	"""Creates a new Mail Backend Request."""

	if do_not_enqueue:
		frappe.flags.do_not_enqueue = True

	request = frappe.new_doc("Mail Backend Request")
	request.backend_type = backend_type
	request.backend_name = backend_name
	request.method = method
	request.endpoint = endpoint
	request.request_headers = request_headers
	request.request_params = request_params
	request.request_data = request_data
	request.request_json = request_json
	request.on_start = get_dotted_path(on_start) if callable(on_start) else on_start
	request.on_start_kwargs = json.dumps(on_start_kwargs) if on_start_kwargs else None
	request.on_end = get_dotted_path(on_end) if callable(on_end) else on_end
	request.on_end_kwargs = json.dumps(on_end_kwargs) if on_end_kwargs else None
	request.insert(ignore_permissions=True)

	return request
