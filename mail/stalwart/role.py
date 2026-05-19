import json

import frappe
from frappe import _

from mail.stalwart.cli import StalwartCLI


class RoleService(StalwartCLI):
	def get(self, id: str, fields: list[str] | None = None) -> dict:
		"""Fetches a role by ID from the Stalwart server, selecting specific fields if provided."""

		if not isinstance(fields, list):
			fields = ["id", "description", "disabledPermissions", "enabledPermissions", "roleIds"]

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

		if not isinstance(fields, list):
			fields = ["id", "description", "disabledPermissions", "enabledPermissions", "roleIds"]

		commands = ["query", "role"]

		if filters:
			allowed_filter_keys = {"description"}
			for key, value in filters.items():
				if key in allowed_filter_keys:
					commands.extend(["--where", f"{key}={value}"])
				else:
					frappe.throw(
						_("Invalid filter key: {0}. Allowed keys are: {1}").format(
							key, ", ".join(allowed_filter_keys)
						)
					)

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			if response["output"]:
				roles = response["output"].splitlines()
				return [json.loads(role) for role in roles]

			return []
		else:
			frappe.throw(title=_("Failed to fetch roles"), msg=response["output"] or response["error"])
