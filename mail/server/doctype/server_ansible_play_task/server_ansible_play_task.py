# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from uuid_utils import uuid7


class ServerAnsiblePlayTask(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_unique_task()

	def validate_unique_task(self) -> None:
		"""Validates that the task is unique within the play."""

		if frappe.db.exists(
			"Server Ansible Play Task", {"play": self.name, "task": self.task, "name": ["!=", self.name]}
		):
			frappe.throw(
				_("Task {0} already exists in play {1}").format(self.task, self.play),
				frappe.DuplicateEntryError,
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


def on_doctype_update() -> None:
	frappe.db.add_unique("Server Ansible Play Task", ["play", "task"])
