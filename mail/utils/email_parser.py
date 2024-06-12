from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from email.message import Message


def get_parsed_message(message: str) -> "Message":
	"""Returns parsed email message object from string."""

	from email import message_from_string

	return message_from_string(message)
