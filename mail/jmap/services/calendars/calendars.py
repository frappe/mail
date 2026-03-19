from typing import ClassVar

from mail.jmap.services.core import CoreService


class CalendarsService(CoreService):
	"""Service for handling calendar-related functionality based on the JMAP server capabilities."""

	capabilities: ClassVar[list[str]] = ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:calendars"]

	def __post_init__(self) -> None:
		"""Post-initialization to check if the JMAP server supports the Calendars capability and raise an error if not."""

		super().__post_init__()

		if "urn:ietf:params:jmap:calendars" not in self.connection.capabilities:
			raise NotImplementedError("The JMAP server does not support the Calendars capability.")

	@property
	def primary_account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.connection.primary_accounts["urn:ietf:params:jmap:calendars"]
