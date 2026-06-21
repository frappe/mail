from mail.utils.logger.base import EventLogger


class OutboundLogger(EventLogger):
	"""Structured event logger for outbound mail operations ("mail.outbound")."""

	logger_name = "mail.outbound"
	config_prefix = "outbound"


def get_outbound_logger(ctx: dict | None = None) -> OutboundLogger:
	"""Returns a structured event logger for outbound mail operations.

	The returned `OutboundLogger` is bound to `ctx` (by reference); mutating that
	same dict between log calls is reflected in subsequent records.
	"""

	return OutboundLogger(ctx)
