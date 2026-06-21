from mail.utils import get_config


def get_avatar_url(email: str) -> str | None:
	"""Returns the Gravatar avatar URL for the given email, or None if Gravatar is disabled.

	Gravatar is a third-party service, so the lookup is opt-in via the "Enable Gravatar" Mail
	Setting. When disabled, callers fall back to showing initials instead.
	"""

	if not get_config("enable_gravatar"):
		return None

	return f"/api/method/mail.api.mail.get_avatar?email={email}"
