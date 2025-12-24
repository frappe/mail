from datetime import UTC, date, datetime, timezone
from email.utils import parsedate_to_datetime as parsedate
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import convert_utc_to_system_timezone, get_datetime, get_datetime_str, get_system_timezone


def get_utc_now(naive: bool = False) -> datetime:
	"""Returns the current UTC datetime."""

	now = datetime.now(UTC)
	return now.replace(tzinfo=None) if naive else now


def utcnow() -> "str":
	"""Returns current UTC time in ISO format."""

	return get_utc_now().isoformat().replace("+00:00", "Z")


def convert_to_utc(
	date_time: datetime | str, from_timezone: str | None = None, naive: bool = False
) -> "datetime":
	"""Converts the given datetime to UTC timezone."""

	dt = get_datetime(date_time)
	if dt.tzinfo is None:
		tz = ZoneInfo(from_timezone or get_system_timezone())
		dt = dt.replace(tzinfo=tz)

	utc_dt = dt.astimezone(UTC)
	return utc_dt.replace(tzinfo=None) if naive else utc_dt


def parsedate_to_datetime(date_header: str) -> "datetime":
	"""Returns datetime object from parsed date header."""

	utc_dt = parsedate(date_header)
	if not utc_dt:
		frappe.throw(_("Invalid date format: {0}").format(date_header))

	return convert_utc_to_system_timezone(utc_dt)


def parse_iso_datetime(
	datetime_str: str, to_timezone: str | None = None, as_str: bool = True
) -> str | datetime:
	"""Converts ISO datetime string to datetime object in given timezone."""

	if not to_timezone:
		to_timezone = get_system_timezone()

	dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00")).astimezone(ZoneInfo(to_timezone))

	return get_datetime_str(dt) if as_str else dt


def add_or_update_tzinfo(date_time: datetime | str, time_zone: str | None = None) -> str:
	"""Adds or updates timezone to the datetime."""

	date_time = get_datetime(date_time)
	target_tz = ZoneInfo(time_zone or get_system_timezone())

	if date_time.tzinfo is None:
		date_time = date_time.replace(tzinfo=target_tz)
	else:
		date_time = date_time.astimezone(target_tz)

	return str(date_time)


def to_iso8601_z(dt: datetime) -> str:
	"""
	Convert a datetime (naive or aware) to an ISO 8601 string ending with 'Z' (UTC).

	Rules:
	- If naive, assume UTC.
	- Always return a string like "YYYY-MM-DDTHH:MM:SS.sssZ".
	"""

	if isinstance(dt, date):
		dt = get_datetime(dt)

	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=UTC)
	else:
		dt = dt.astimezone(UTC)

	return dt.isoformat().replace("+00:00", "Z")
