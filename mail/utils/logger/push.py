from mail.utils.logger.base import EventLogger


class PushLogger(EventLogger):
	"""Structured event logger for mail push notifications ("mail.push")."""

	logger_name = "mail.push"
	config_prefix = "push"


def get_push_logger(ctx: dict | None = None) -> PushLogger:
	"""Returns a structured event logger for mail push notifications.

	The returned `PushLogger` is bound to `ctx` (by reference); mutating that
	same dict between log calls is reflected in subsequent records.
	"""

	return PushLogger(ctx)
