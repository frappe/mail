from urllib.parse import quote


def get_avatar_url(email: str) -> str:
	"""Returns the avatar URL for the given email."""

	return f"/api/method/mail.api.mail.get_avatar?email={quote(email, safe='')}"
