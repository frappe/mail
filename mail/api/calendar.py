import json

import frappe
from frappe import _

from mail.client.doctype.calendar.calendar import fetch_calendars
from mail.client.doctype.calendar_event.calendar_event import (
	delete_calendar_event_instance,
	delete_calendar_events,
	fetch_calendar_events,
	get_master_events_by_uids,
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

	user = frappe.session.user
	events = fetch_calendar_events(
		user,
		{"after": from_date, "before": to_date},
		limit=999,
		time_zone=time_zone,
		expand_recurrences=True,
	)[0]

	recurring_event_uids = {event["uid"] for event in events if event["recurrence_id"]}
	recurring_event_masters = get_master_events_by_uids(user, list(recurring_event_uids))
	recurrence_rule_map = {uid: master["recurrence_rule"] for uid, master in recurring_event_masters.items()}

	for event in events:
		if rule := recurrence_rule_map.get(event["uid"]):
			event["recurrence_rule"] = rule

	return events


@frappe.whitelist()
def delete_event(uid: str, until=None) -> None:
	"""Deletes a calendar event by its UID or sets the end date for recurring events."""

	user = frappe.session.user
	event = get_master_events_by_uids(user, [uid])[uid]
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


@frappe.whitelist()
def delete_event_instance(uid: str, recurrence_id: str) -> None:
	"""Deletes a specific instance of a recurring calendar event."""

	user = frappe.session.user
	master_id = get_master_events_by_uids(user, [uid])[uid]["id"]
	delete_calendar_event_instance(user, master_id, recurrence_id)
