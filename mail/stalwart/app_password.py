import json
import re
from dataclasses import dataclass

import frappe
from frappe import _

from mail.stalwart.account import Permissions, PermissionType
from mail.stalwart.cli import StalwartCLI


@dataclass
class AppPassword:
	description: str
	permissions: Permissions | None = None

	def to_dict(self) -> dict:
		self.permissions = self.permissions or Permissions(type=PermissionType.INHERIT)
		return {
			"description": self.description,
			"permissions": self.permissions.to_dict(),
		}


class AppPasswordService(StalwartCLI):
	def create(self, app_password: AppPassword) -> str:
		"""Creates an app password on Stalwart and returns the generated secret."""

		app_password_data = app_password.to_dict()
		app_password_json = json.dumps(app_password_data)
		response = self.run(["create", "AppPassword", "--json", app_password_json])

		if not response["success"]:
			frappe.throw(
				title=_("Failed to create app password"), msg=response["output"] or response["error"]
			)

		# TODO: Parse and return the generated app password from the response output (stalwart-cli v1.0.7)
		return response["output"]
