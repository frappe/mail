from typing import ClassVar

from mail.jmap.services.core import CoreService


class WebSocketService(CoreService):
	"""Service for handling WebSocket-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "WebSocket"
	capabilities: ClassVar[list[str]] = ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:websocket"]

	def __post_init__(self) -> None:
		"""Post-initialization to check if the JMAP server supports WebSocket and raise an error if not."""

		super().__post_init__()

		if not self.supports_websocket:
			raise NotImplementedError("The JMAP server does not support WebSocket.")

	@property
	def primary_account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.connection.primary_accounts["urn:ietf:params:jmap:websocket"]

	@property
	def websocket(self) -> dict:
		"""Returns the WebSocket capabilities of the JMAP server."""

		return self.connection.capabilities.get("urn:ietf:params:jmap:websocket") or {}

	@property
	def supports_websocket(self) -> bool:
		"""Returns True if the JMAP server supports WebSocket, False otherwise."""

		return bool(self.websocket)

	@property
	def websocket_url(self) -> str | None:
		"""Returns the WebSocket URL of the JMAP server, or None if not supported."""

		return self.websocket.get("url")

	@property
	def websocket_supports_push(self) -> bool:
		"""Returns True if the JMAP server supports WebSocket push, False otherwise."""

		return self.websocket.get("supportsPush", False)
