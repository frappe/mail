from typing import ClassVar

from mail.jmap.services.calendars.calendars import CalendarsService


class PrincipalService(CalendarsService):
	"""Service for handling principal-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "Principal"

	def get(
		self,
		principal_id: str,
		utc_start: str,
		utc_end: str,
		show_details: bool = False,
		event_properties: list[str] | None = None,
	) -> dict:
		"""Public method to get principal availability, allowing for optional details and event properties to be specified."""

		payload = {
			"accountId": self.primary_account_id,
			"id": principal_id,
			"start": utc_start,
			"end": utc_end,
			"showDetails": show_details,
		}

		if show_details and event_properties:
			payload["eventProperties"] = event_properties

		response = self._call(self.capabilities, [[f"{self.type}/getAvailability", payload, "0"]])

		if method_responses := response.get("methodResponses"):
			return method_responses[0][1]

		return {}
