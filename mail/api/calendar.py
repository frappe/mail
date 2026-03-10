import frappe

from mail.client.doctype.calendar.calendar import fetch_calendars
from mail.client.doctype.calendar_event.calendar_event import fetch_calendar_events


@frappe.whitelist()
def get_calendars() -> list[dict[str, str]]:
	"""Returns a list of the current user's calendars."""

	calendars = fetch_calendars(frappe.session.user)

	return [{key: cal[key] for key in ["name", "_name"]} for cal in calendars]


@frappe.whitelist()
def get_calendar_events(from_date: str, to_date: str) -> list[dict]:
	"""Fetches calendar events between from_date and to_date for the current user."""

	events = fetch_calendar_events(frappe.session.user, {"after": from_date, "before": to_date})

	return events[0]
