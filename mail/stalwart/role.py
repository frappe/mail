import json
from typing import ClassVar

import frappe
from frappe import _

from mail.stalwart.cli import StalwartCLI


class RoleService(StalwartCLI):
	DEFAULT_FIELDS: ClassVar[list[str]] = [
		"id",
		"description",
		"disabledPermissions",
		"enabledPermissions",
		"roleIds",
	]
	ALLOWED_FILTER_KEYS: ClassVar[set[str]] = {"description"}

	@classmethod
	def _resolved_fields(cls, fields: list[str] | None) -> list[str]:
		return fields if isinstance(fields, list) else cls.DEFAULT_FIELDS

	@classmethod
	def _append_filters(cls, commands: list[str], filters: dict[str, str]) -> None:
		for key, value in filters.items():
			if key in cls.ALLOWED_FILTER_KEYS:
				commands.extend(["--where", f"{key}={value}"])
			else:
				frappe.throw(
					_("Invalid filter key: {0}. Allowed keys are: {1}").format(
						key, ", ".join(cls.ALLOWED_FILTER_KEYS)
					)
				)

	@staticmethod
	def _parse_query_output(output: str) -> list[dict]:
		if not output:
			return []

		return [json.loads(role) for role in output.splitlines()]

	def get(self, id: str, fields: list[str] | None = None) -> dict:
		"""Fetches a role by ID from the Stalwart server, selecting specific fields if provided."""

		fields = self._resolved_fields(fields)

		commands = ["get", "role", id]

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			if response["output"]:
				return json.loads(response["output"])
			else:
				frappe.throw(title=_("Role not found"), msg=_("Role with ID {0} not found.").format(id))
		else:
			frappe.throw(title=_("Failed to fetch role"), msg=response["output"] or response["error"])

	def get_all(self, filters: dict[str, str] | None = None, fields: list[str] | None = None) -> list[dict]:
		"""Fetches all roles from the Stalwart server, applying optional filters and selecting specific fields."""

		filters = filters or {}
		fields = self._resolved_fields(fields)

		commands = ["query", "role"]

		if filters:
			self._append_filters(commands, filters)

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			return self._parse_query_output(response["output"])
		else:
			frappe.throw(title=_("Failed to fetch roles"), msg=response["output"] or response["error"])
