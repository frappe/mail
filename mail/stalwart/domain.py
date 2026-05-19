import json

import frappe
from frappe import _

from mail.stalwart.cli import StalwartCLI


class DomainService(StalwartCLI):
	def get(self, id: str, fields: list[str] | None = None) -> dict:
		"""Fetches a domain by ID from the Stalwart server, selecting specific fields if provided."""

		if not isinstance(fields, list):
			fields = ["id", "isEnabled", "name", "description"]

		commands = ["get", "Domain", id]

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			if response["output"]:
				return json.loads(response["output"])
			else:
				frappe.throw(title=_("Domain not found"), msg=_("Domain with ID {0} not found.").format(id))
		else:
			frappe.throw(title=_("Failed to fetch domain"), msg=response["output"] or response["error"])

	def get_all(self, filters: dict[str, str] | None = None, fields: list[str] | None = None) -> list[dict]:
		"""Fetches all domains from the Stalwart server, applying optional filters and selecting specific fields."""

		filters = filters or {}

		if not isinstance(fields, list):
			fields = ["id", "isEnabled", "name", "description"]

		commands = ["query", "Domain"]

		if filters:
			allowed_filter_keys = {"text", "name"}
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
				domains = response["output"].splitlines()
				return [json.loads(domain) for domain in domains]

			return []
		else:
			frappe.throw(title=_("Failed to fetch domains"), msg=response["output"] or response["error"])

	def delete(self, ids: list[str]) -> None:
		"""Deletes domains with the specified IDs from the Stalwart server."""

		if not ids:
			frappe.throw(title=_("No domain IDs provided"), msg=_("No domain IDs provided for deletion."))

		response = self.run(["delete", "Domain", "--ids", ",".join(ids)])

		if not response["success"]:
			frappe.throw(title=_("Failed to delete domains"), msg=response["output"] or response["error"])
