from typing import Any

import frappe
from frappe.utils import cint

from mail.utils import get_mail_config


class EventLogger:
	"""Structured event logger for a mail subsystem.

	Binds a context dict (shared by reference, so callers can keep mutating it)
	and emits one structured record per event. Each log method takes the event
	name as its first argument and any event-specific fields as keyword
	arguments, keeping call sites free of repetitive `{**ctx, "event": ...}`
	boilerplate. Pick the method that matches the event:

	- `debug`   — flow tracing and routine/no-op outcomes (entry points, cache
	              invalidations, lock contention, unchanged state).
	- `info`    — meaningful work that happened (mail sent, messages synced,
	              notifications delivered).
	- `warning` — handled-but-unexpected situations (bad client input, frozen
	              user, unknown payload type).
	- `error`   — failures during our own processing.
	- `exception` — same as `error` but also records the active traceback; use
	              it inside an `except` block.

	Subclasses set `logger_name` (the frappe logger channel, e.g. "mail.push")
	and `config_prefix` (the Mail Settings key prefix, e.g. "push"), which
	selects the `<prefix>_log_max_size`, `<prefix>_log_file_count` and
	`<prefix>_log_level` config values.
	"""

	logger_name: str
	config_prefix: str

	def __init__(self, ctx: dict | None = None) -> None:
		config = get_mail_config()

		max_size = cint(config[f"{self.config_prefix}_log_max_size"])
		file_count = cint(config[f"{self.config_prefix}_log_file_count"])
		self.logger = frappe.logger(
			self.logger_name, allow_site=True, max_size=max_size, file_count=file_count
		)
		self.logger.setLevel(config[f"{self.config_prefix}_log_level"].upper())

		self.ctx = ctx if ctx is not None else {}

	def _record(self, event: str, fields: dict) -> dict:
		return {**self.ctx, **fields, "event": event}

	def debug(self, event: str, **fields: Any) -> None:
		self.logger.debug(self._record(event, fields))

	def info(self, event: str, **fields: Any) -> None:
		self.logger.info(self._record(event, fields))

	def warning(self, event: str, **fields: Any) -> None:
		self.logger.warning(self._record(event, fields))

	def error(self, event: str, **fields: Any) -> None:
		self.logger.error(self._record(event, fields))

	def exception(self, event: str, **fields: Any) -> None:
		self.logger.exception(self._record(event, fields))


class PushLogger(EventLogger):
	"""Structured event logger for mail push notifications ("mail.push")."""

	logger_name = "mail.push"
	config_prefix = "push"


class StorageLogger(EventLogger):
	"""Structured event logger for mail storage operations ("mail.storage")."""

	logger_name = "mail.storage"
	config_prefix = "storage"


class OutboundLogger(EventLogger):
	"""Structured event logger for outbound mail operations ("mail.outbound")."""

	logger_name = "mail.outbound"
	config_prefix = "outbound"


class InboundLogger(EventLogger):
	"""Structured event logger for inbound mail operations ("mail.inbound")."""

	logger_name = "mail.inbound"
	config_prefix = "inbound"


def get_push_logger(ctx: dict | None = None) -> PushLogger:
	"""Returns a structured event logger for mail push notifications.

	The returned logger is bound to `ctx` (by reference); mutating that same
	dict between log calls is reflected in subsequent records.
	"""

	return PushLogger(ctx)


def get_storage_logger(ctx: dict | None = None) -> StorageLogger:
	"""Returns a structured event logger for mail storage operations.

	The returned logger is bound to `ctx` (by reference); mutating that same
	dict between log calls is reflected in subsequent records.
	"""

	return StorageLogger(ctx)


def get_outbound_logger(ctx: dict | None = None) -> OutboundLogger:
	"""Returns a structured event logger for outbound mail operations.

	The returned logger is bound to `ctx` (by reference); mutating that same
	dict between log calls is reflected in subsequent records.
	"""

	return OutboundLogger(ctx)


def get_inbound_logger(ctx: dict | None = None) -> InboundLogger:
	"""Returns a structured event logger for inbound mail operations.

	The returned logger is bound to `ctx` (by reference); mutating that same
	dict between log calls is reflected in subsequent records.
	"""

	return InboundLogger(ctx)
