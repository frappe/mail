from typing import ClassVar

from mail.jmap.services.core import CoreService


class VacationResponseService(CoreService):
	"""Service for handling vacation response related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "VacationResponse"

	capabilities: ClassVar[list[str]] = ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:vacationresponse"]

	def __post_init__(self) -> None:
		"""Post-initialization to check if the JMAP server supports the Vacation Response capability and raise an error if not."""

		super().__post_init__()

		if "urn:ietf:params:jmap:vacationresponse" not in self.connection.capabilities:
			raise NotImplementedError("The JMAP server does not support the Vacation Response capability.")

	@property
	def primary_account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.connection.primary_accounts["urn:ietf:params:jmap:vacationresponse"]

	def get(self) -> dict:
		"""Public method to get the vacation response settings, returning a simplified dictionary with the relevant information."""

		response = self._get()

		if method_responses := response.get("methodResponses"):
			if vacation_responses := method_responses[0][1].get("list"):
				return vacation_responses[0]

		return {}

	def update(self, settings: dict) -> dict:
		"""Public method to update the vacation response settings, returning the updated settings as a simplified dictionary."""

		payload = {
			"singleton": {
				"isEnabled": settings.get("is_enabled", False),
				"fromDate": settings.get("from_date"),
				"toDate": settings.get("to_date"),
				"subject": settings.get("subject"),
				"textBody": settings.get("text_body"),
				"htmlBody": settings.get("html_body"),
			}
		}

		response = self._update(payload)

		result = {"updated": [], "notUpdated": {}}
		if method_responses := response.get("methodResponses"):
			result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
			if not_updated := method_responses[0][1].get("notUpdated", {}):
				result["notUpdated"].update(not_updated)

		return result
