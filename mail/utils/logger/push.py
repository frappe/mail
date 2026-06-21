from typing import Any

import frappe
from frappe.utils import cint

from mail.utils import get_config


class PushLogger:
	"""Structured event logger for mail push notifications ("mail.push").

	Binds a context dict (shared by reference, so callers can keep mutating it)
	and emits one structured record per event. Each log method takes the event
	name as its first argument and any event-specific fields as keyword
	arguments, keeping call sites free of repetitive `{**ctx, "event": ...}`
	boilerplate. Pick the method that matches the event:

	- `debug`   — flow tracing and routine/no-op outcomes (entry points, cache
	              invalidations, lock contention, unchanged state).
	- `info`    — meaningful work that happened (messages synced, notifications
	              sent, subscription verified, scheduled batches).
	- `warning` — handled-but-unexpected situations (frozen user, bad client
	              input, unknown push type or entity).
	- `error`   — failures during our own processing.
	- `exception` — same as `error` but also records the active traceback.
	"""

	def __init__(self, ctx: dict | None = None) -> None:
		config = get_config()

		max_size = cint(config["push_log_max_file_size"])
		file_count = cint(config["push_log_file_count"])
		self.logger = frappe.logger("mail.push", allow_site=True, max_size=max_size, file_count=file_count)
		self.logger.setLevel(config["push_log_level"].upper())

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


def get_push_logger(ctx: dict | None = None) -> PushLogger:
	"""Returns a structured event logger for mail push notifications.

	The returned `PushLogger` is bound to `ctx` (by reference); mutating that
	same dict between log calls is reflected in subsequent records.
	"""

	return PushLogger(ctx)
