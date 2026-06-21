from urllib.parse import quote

from mail.utils import get_mail_config


def get_avatar_url(email: str) -> str | None:
	"""Returns the Gravatar avatar URL for the given email, or None if Gravatar is disabled.

	Gravatar is a third-party service, so the lookup is opt-in via the `enable_gravatar` mail
	config (site_config.json). When disabled, callers fall back to showing initials instead.
	"""

	if not get_mail_config("enable_gravatar"):
		return None

	return f"/api/method/mail.api.mail.get_avatar?email={quote(email, safe='')}"
