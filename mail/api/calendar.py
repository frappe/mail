import json

import frappe
from frappe import _

from mail.client.doctype.calendar.calendar import fetch_calendars
from mail.client.doctype.calendar_event.calendar_event import (
	fetch_calendar_events,
	get_master_events_by_uids,
	update_calendar_event,
)
from mail.client.doctype.calendar_event.calendar_event import (
	get_calendar_events as get_calendar_events_by_ids,
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

	uids = {event["uid"] for event in events}
	masters = get_master_events_by_uids(user, list(uids))
	master_map = {
		uid: {
			"recurrence_rule": json.loads(master["recurrence_rule"]),
			"master_id": master["id"],
			"master_start": master["start"],
			"master_duration": master["duration"],
		}
		for uid, master in masters.items()
	}

	for event in events:
		event.update(master_map.get(event["uid"], {}))

	return events


@frappe.whitelist()
def edit_calendar_event(id: str, **kwargs) -> None:
	user = frappe.session.user
	event = get_calendar_events_by_ids(user, [id])[0]

	def resolve(key):
		return kwargs[key] if key in kwargs else event[key]

	calendar_ids = (
		kwargs["calendar_ids"]
		if "calendar_ids" in kwargs
		else [calendar["calendar_id"] for calendar in event["calendars"]]
	)

	update_calendar_event(
		user,
		id,
		event["uid"],
		event["organizer"],
		calendar_ids,
		resolve("status"),
		resolve("draft"),
		resolve("title"),
		resolve("start"),
		resolve("duration"),
		resolve("time_zone"),
		json.loads(resolve("recurrence_rule")),
		resolve("show_without_time"),
		resolve("privacy"),
		resolve("free_busy_status"),
		resolve("description"),
		resolve("locations"),
		resolve("links"),
		resolve("participants"),
		resolve("alerts"),
		resolve("use_default_alerts"),
		kwargs.get("send_scheduling_messages", False),
	)
