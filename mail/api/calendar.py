import json

import frappe
from frappe import _

from mail.client.doctype.calendar.calendar import fetch_calendars
from mail.client.doctype.calendar_event.calendar_event import (
	delete_calendar_events,
	fetch_calendar_events,
	get_calendar_event_by_uid,
	update_calendar_event,
)


@frappe.whitelist()
def get_calendars() -> list[dict[str, str]]:
	"""Returns a list of the current user's calendars."""

	calendars = fetch_calendars(frappe.session.user)

	return [{key: cal[key] for key in ["name", "_name"]} for cal in calendars]


@frappe.whitelist()
def get_calendar_events(from_date: str, to_date: str, time_zone: str) -> list[dict]:
	"""Fetches calendar events between from_date and to_date for the current user."""

	events = fetch_calendar_events(
		frappe.session.user,
		{"after": from_date, "before": to_date},
		limit=999,
		time_zone=time_zone,
		expand_recurrences=True,
	)

	return events[0]


@frappe.whitelist()
def delete_event(uid: str, until=None) -> None:
	"""Deletes a calendar event by its UID or sets the end date for recurring events."""

	user = frappe.session.user
	event = get_calendar_event_by_uid(user, uid)
	if not until:
		return delete_calendar_events(user, [event["id"]])

	recurrence_rule = json.loads(event["recurrence_rule"])
	recurrence_rule["until"] = until
	update_calendar_event(
		user,
		event["id"],
		event["uid"],
		event["organizer"],
		[calendar["calendar_id"] for calendar in event["calendars"]],
		event["status"],
		event["draft"],
		event["title"],
		event["start"],
		event["duration"],
		event["time_zone"],
		recurrence_rule,
		event["show_without_time"],
		event["privacy"],
		event["free_busy_status"],
		event["description"],
		event["locations"],
		event["links"],
		event["participants"],
		event["alerts"],
		event["use_default_alerts"],
	)
