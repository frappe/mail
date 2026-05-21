import json
import re
from dataclasses import dataclass, field
from typing import ClassVar

import frappe
from frappe import _

from mail.stalwart.account import Permissions
from mail.stalwart.cli import StalwartCLI


@dataclass
class AppPassword:
	description: str
	permissions: Permissions = field(default_factory=Permissions)

	def to_dict(self) -> dict:
		return {
			"description": self.description,
			"permissions": self.permissions.to_dict(),
		}


class AppPasswordService(StalwartCLI):
	SECRET_PATTERN: ClassVar[re.Pattern] = re.compile(r"Secret:\s*(\S+)")

	@classmethod
	def _parse_secret(cls, output: str) -> str | None:
		match = cls.SECRET_PATTERN.search(output)
		return match.group(1) if match else None

	def create(self, app_password: AppPassword) -> str:
		"""Creates an app password on Stalwart and returns the generated secret."""

		app_password_data = app_password.to_dict()
		app_password_json = json.dumps(app_password_data)
		response = self.run(["create", "AppPassword", "--json", app_password_json])

		if not response["success"]:
			frappe.throw(
				title=_("Failed to create app password"), msg=response["output"] or response["error"]
			)

		secret = self._parse_secret(response["output"])
		if not secret:
			frappe.throw(
				title=_("Failed to parse app password secret"),
				msg=_("Could not extract the generated app password secret from the response."),
			)

		return secret
