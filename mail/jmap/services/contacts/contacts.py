from typing import ClassVar

from mail.jmap.services.core import CoreService


class ContactsService(CoreService):
	"""Service for handling contact-related functionality based on the JMAP server capabilities."""

	capabilities: ClassVar[list[str]] = ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:contacts"]

	def __post_init__(self) -> None:
		"""Post-initialization to check if the JMAP server supports the Contacts capability and raise an error if not."""

		super().__post_init__()

		if "urn:ietf:params:jmap:contacts" not in self.connection.capabilities:
			raise NotImplementedError("The JMAP server does not support the Contacts capability.")

	@property
	def primary_account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.connection.primary_accounts["urn:ietf:params:jmap:contacts"]
