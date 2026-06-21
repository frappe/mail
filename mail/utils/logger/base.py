from typing import Any

import frappe
from frappe.utils import cint

from mail.utils import get_config


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
	selects the `<prefix>_log_max_file_size`, `<prefix>_log_file_count` and
	`<prefix>_log_level` config values.
	"""

	logger_name: str
	config_prefix: str

	def __init__(self, ctx: dict | None = None) -> None:
		config = get_config()

		max_size = cint(config[f"{self.config_prefix}_log_max_file_size"])
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
