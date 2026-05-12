import json

import frappe
from frappe import _

from mail.stalwart.cli import StalwartCLI


class DomainService(StalwartCLI):
	def get(self, id: str, fields: list[str] | None = None) -> dict:
		"""Fetches a domain by ID from the Stalwart server, selecting specific fields if provided."""

		if not isinstance(fields, list):
			fields = ["id", "isEnabled", "name", "description"]

		commands = ["get", "domain", id]

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			if response["output"]:
				return json.loads(response["output"])
			else:
				frappe.throw(_("Domain with ID {0} not found.").format(id))
		else:
			frappe.throw(_("Failed to fetch domain: {0}").format(response["error"]))

	def get_all(self, filters: dict[str, str] | None = None, fields: list[str] | None = None) -> list[dict]:
		"""Fetches all domains from the Stalwart server, applying optional filters and selecting specific fields."""

		filters = filters or {}

		if not isinstance(fields, list):
			fields = ["id", "isEnabled", "name", "description"]

		commands = ["query", "domain"]

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
			frappe.throw(_("Failed to fetch domains: {0}").format(response["error"]))
