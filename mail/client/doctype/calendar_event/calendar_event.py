# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from datetime import timedelta
from typing import Literal
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.client.doctype.calendar.calendar import validate_calendar_name_format
from mail.jmap import get_jmap_client
from mail.utils import parse_filters
from mail.utils.cache import get_root_domain_name
from mail.utils.dt import convert_to_utc, get_utc_now, parse_iso_datetime
from mail.utils.validation import has_permission_for_user


class CalendarEvent(Document):
	@property
	def calendar_ids(self) -> list[str]:
		"""Returns a list of calendar IDs associated with the event."""

		calendar_ids = []
		for calendar in self.calendars:
			calendar_id = calendar.get("calendar_id")
			if not calendar_id:
				frappe.throw(_("Row #{0}: Calendar ID is required.").format(calendar.idx))
			calendar_ids.append(calendar_id)

		return calendar_ids

	@property
	def formatted_recurrence_rule(self) -> dict | None:
		"""Returns the formatted recurrence rule for the event."""

		if self.recurrence_rule:
			return json.loads(self.recurrence_rule)

	@property
	def formatted_locations(self) -> list[dict] | None:
		"""Returns the formatted locations for the event."""

		if self.locations:
			return [{"uid": l.uid, "name": l._name} for l in self.locations]

	@property
	def formatted_links(self) -> list[dict] | None:
		"""Returns the formatted links for the event."""

		if self.links:
			return [{"uid": l.uid, "href": l.href, "content_type": l.content_type} for l in self.links]

	@property
	def formatted_alerts(self) -> list[dict] | None:
		"""Returns the formatted alerts for the event."""

		if self.alerts and not self.use_default_alerts:
			return [
				{
					"uid": a.uid,
					"action": a.action,
					"type": a.type,
					"relative_to": a.relative_to,
					"offset": a.offset,
					"when": a.when,
				}
				for a in self.alerts
			]

	@property
	def formatted_participants(self) -> list[dict] | None:
		"""Returns the formatted participants for the event."""

		if self.participants:
			return [
				{
					"uid": p.uid,
					"name": p._name,
					"email": p.email,
					"kind": p.kind,
					"roles": json.loads(p.roles),
					"schedule_id": p.schedule_id,
					"send_to": json.loads(p.send_to),
					"participation_status": p.participation_status,
					"expect_reply": bool(p.expect_reply),
					"description": p.description,
				}
				for p in self.participants
			]

	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_calendar_event(
			user=self.user,
			calendar_ids=self.calendar_ids,
			status=self.status,
			title=self.title,
			start=self.start,
			duration=self.duration,
			time_zone=self.time_zone,
			privacy=self.privacy,
			organizer=self.organizer,
			description=self.description,
			free_busy_status=self.free_busy_status,
			recurrence_rule=self.formatted_recurrence_rule,
			locations=self.formatted_locations,
			links=self.formatted_links,
			alerts=self.formatted_alerts,
			participants=self.formatted_participants,
			draft=bool(self.draft),
			show_without_time=bool(self.show_without_time),
			use_default_alerts=bool(self.use_default_alerts),
			send_scheduling_messages=bool(self.send_scheduling_messages),
		)
		self.name = f"{self.user}|{self.id}"
		self.reload()

	def load_from_db(self) -> "CalendarEvent":
		user, id = self.name.split("|")
		if events := get_calendar_events(user, [id]):
			return super(Document, self).__init__(events[0])

		frappe.throw(
			_("Calendar Event with ID {0} not found in user {1}.").format(frappe.bold(id), frappe.bold(user)),
			title=_("Calendar Event Not Found"),
		)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_calendar_events(user, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)

		title = filters.get("title")
		user = filters.get("user") or frappe.session.user
		after = filters.get("after") and convert_to_utc(filters.get("after"), naive=True).strftime(
			"%Y-%m-%dT%H:%M:%SZ"
		)
		before = filters.get("before") and convert_to_utc(filters.get("before"), naive=True).strftime(
			"%Y-%m-%dT%H:%M:%SZ"
		)

		if not after and not before:
			now = get_utc_now(naive=True)

			first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
			after = first_day.strftime("%Y-%m-%dT%H:%M:%SZ")

			first_next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
			last_day = first_next_month - timedelta(days=1)
			before = last_day.strftime("%Y-%m-%dT00:00:00Z")

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view calendar events."), alert=True)
			return []

		filter = {}
		if title:
			filter["title"] = title
		if after:
			filter["after"] = after
		if before:
			filter["before"] = before
		limit = cint(kwargs.get("start")) + page_length
		events, total = fetch_calendar_events(user, filter, limit=limit)
		frappe.cache.set_value(_get_total_cache_key(user), total, expires_in_sec=600)

		if not events:
			frappe.msgprint(_("No calendar events found."), alert=True)

		return events

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user
		return (
			frappe.cache.get_value(_get_total_cache_key(user))
			if user and has_permission_for_user(user, raise_exception=False)
			else 0
		)

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	def validate(self) -> None:
		self.validate_draft()
		self.validate_calendars()
		self.validate_send_scheduling_messages()

	def validate_draft(self) -> None:
		"""Validates that an existing event cannot be marked as draft."""

		if not self.is_new() and self.draft:
			if self.has_value_changed("draft"):
				frappe.throw(_("Cannot mark an existing event as draft."))

	def validate_calendars(self) -> None:
		"""Validates that at least one calendar is associated with the event."""

		if not self.calendars:
			frappe.throw(_("A event must belong to at least one calendar."))

		for c in self.calendars:
			validate_calendar_name_format(c.calendar)
			_user, calendar_id = c.calendar.split("|")
			c.calendar_id = calendar_id

	def validate_send_scheduling_messages(self) -> None:
		"""Disables sending scheduling messages for draft events."""

		if self.draft:
			self.send_scheduling_messages = 0


def _get_total_cache_key(user: str) -> str:
	"""Returns a cache key for total calendar events count for the given user."""

	return f"{user}:calendar_events:total"


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes calendar events for the given list of names."""

	if isinstance(names, str):
		names = json.loads(names)

	user_ids_map = {}
	for name in names:
		user, id = name.split("|")
		user_ids_map.setdefault(user, []).append(id)

	for user, ids in user_ids_map.items():
		delete_calendar_events(user, ids)

	frappe.msgprint(_("Calendar Events deleted successfully."), alert=True)


@frappe.whitelist()
def add_calendar_event(
	user: str,
	calendar_ids: list[str],
	status: Literal["Tentative", "Confirmed", "Cancelled"],
	title: str,
	start: str,
	duration: str,
	time_zone: str,
	privacy: str | None = None,
	organizer: str | None = None,
	description: str | None = None,
	free_busy_status: str | None = None,
	recurrence_rule: dict | None = None,
	locations: list[dict] | None = None,
	links: list[dict] | None = None,
	alerts: list[dict] | None = None,
	participants: list[dict] | None = None,
	draft: bool = False,
	show_without_time: bool = False,
	use_default_alerts: bool = False,
	send_scheduling_messages: bool = False,
) -> str:
	"""Adds a calendar event for the given user and returns the event ID."""

	has_permission_for_user(user)

	uid = f"{uuid7().hex}@{get_root_domain_name()}"
	creation_id = str(uuid7())
	client = get_jmap_client(user)
	response = client.calendar_event_create(
		creation_id=creation_id,
		uid=uid,
		calendar_ids=calendar_ids,
		status=status.lower(),
		title=title,
		start=start,
		duration=duration,
		time_zone=time_zone,
		privacy=privacy.lower() if privacy else None,
		organizer=organizer,
		description=description,
		free_busy_status=free_busy_status.upper() if free_busy_status else None,
		recurrence_rule=recurrence_rule,
		locations=locations,
		links=links,
		alerts=alerts,
		participants=participants,
		draft=draft,
		show_without_time=show_without_time,
		use_default_alerts=use_default_alerts,
		send_scheduling_messages=send_scheduling_messages,
	)

	title = _("Calendar Event Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def fetch_calendar_events(
	user: str,
	filter: dict | None = None,
	position: int = 0,
	limit: int = 50,
	sort: list[dict] | None = None,
	time_zone: str | None = None,
	expand_recurrences: bool = False,
) -> list:
	"""Returns a list of calendar events for the given user based on the provided filters."""

	has_permission_for_user(user)

	calendar_events = []
	client = get_jmap_client(user)

	while len(calendar_events) < limit:
		result = client.calendar_event_query(filter, position, limit, sort, time_zone, expand_recurrences)
		ids = result["ids"]
		total = result["total"]

		if not ids:
			break

		calendar_events.extend(get_calendar_events(user, ids))

		if len(calendar_events) >= limit:
			break

		position += len(ids)

		if position >= total:
			break

	return calendar_events[:limit], total


@frappe.whitelist()
def get_calendar_events(user: str, ids: list[str]) -> list[dict]:
	"""Returns a list of calendar events for the specified user and IDs."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	calendar_map = {c["id"]: c["_name"] for c in client.calendars}

	events = {}
	for event in client.calendar_event_get(ids):
		event = format_calendar_event(user, calendar_map, event)
		events[event["id"]] = event

	return [events[id] for id in ids if id in events]


@frappe.whitelist()
def update_calendar_event() -> None:
	pass


@frappe.whitelist()
def delete_calendar_events(user: str, ids: list[str]) -> None:
	"""Deletes a calendar event for the given user by its ID."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	response = client.calendar_event_delete(ids)

	if response.get("notDestroyed"):
		error_messages = []
		for id, error in response["notDestroyed"].items():
			error_messages.append(f"{id}: {error['description']}")
		frappe.throw(
			_("Calendar Event Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
			title=_("Calendar Event Deletion Error"),
		)

	if response.get("notDestroyed"):
		frappe.throw(_(response["notDestroyed"][id]["description"]), title=_("Calendar Event Deletion Error"))


@frappe.whitelist()
def parse_ics(user: str, ics_data: bytes | str) -> list[dict]:
	"""Parses ICS data and returns calendar event details."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	blob_id = client.upload_blob(ics_data, content_type="text/calendar; charset=utf-8").get("blobId")

	if not blob_id:
		frappe.throw(_("Failed to upload ICS data."), title=_("ICS Upload Error"))

	response = client.calendar_event_parse([blob_id])

	title = _("ICS Parsing Error")
	if parsed := response.get("parsed"):
		events = parsed.get(blob_id)
		if not events:
			frappe.throw(_("No calendar event parsed from the provided ICS data."), title=title)

		return events

	elif response.get("notParsable"):
		frappe.throw(_(response["notParsable"][blob_id]["description"]), title=title)
	elif response.get("notFound"):
		frappe.throw(_(response["notFound"][blob_id]["description"]), title=title)


def format_calendar_event(user: str, calendar_map: dict, event: dict) -> dict:
	"""Formats calendar event data for display."""

	calendars = []
	for calendar_id in event["calendarIds"].keys():
		calendars.append(
			{
				"calendar": f"{user}|{calendar_id}",
				"calendar_id": calendar_id,
				"calendar_name": calendar_map.get(calendar_id),
			}
		)

	locations = [{"uid": uid, "_name": l.get("name")} for uid, l in event.get("locations", {}).items()]
	links = [
		{"uid": uid, "href": l.get("href"), "content_type": l.get("contentType")}
		for uid, l in event.get("links", {}).items()
	]
	alerts = [
		{
			"uid": uid,
			"action": a.get("action", "").title(),
			"type": a.get("trigger", {}).get("@type", ""),
			"relative_to": a.get("trigger", {}).get("relativeTo", "").title(),
			"offset": a.get("trigger", {}).get("offset", "").upper(),
			"when": a.get("trigger", {}).get("when", "").upper(),
		}
		for uid, a in event.get("alerts", {}).items()
	]

	participants = []
	for uid, p in event.get("participants", {}).items():
		roles = {}
		for r, v in p.get("roles", {}).items():
			roles[r.lower()] = v

		participants.append(
			{
				"uid": uid,
				"roles": roles,
				"kind": p["kind"].title() if p.get("kind") else "",
				"_name": p.get("name"),
				"email": p.get("calendarAddress", "").replace("mailto:", "") or p.get("email", ""),
				"schedule_id": p.get("scheduleId", ""),
				"send_to": p.get("sendTo", {}),
				"participation_status": p["participationStatus"].upper()
				if p.get("participationStatus")
				else "",
				"expect_reply": cint(p.get("expectReply", False)),
				"description": p.get("description", ""),
			}
		)

	return {
		"name": f"{user}|{event['id']}",
		"user": user,
		"id": event["id"],
		"uid": event["uid"],
		"title": event["title"],
		"draft": event["isDraft"],
		"origin": event["isOrigin"],
		"may_invite_self": cint(event.get("mayInviteSelf", False)),
		"may_invite_others": cint(event.get("mayInviteOthers", False)),
		"hide_attendees": cint(event.get("hideAttendees", False)),
		"show_without_time": cint(event.get("showWithoutTime", False)),
		"status": event.get("status", "confirmed").title(),
		"start": event["start"],
		"duration": event["duration"],
		"time_zone": event["timeZone"],
		"privacy": event.get("privacy", "").title(),
		"recurrence_rule": json.dumps(event.get("recurrenceRule", {}), indent=2),
		"description": event.get("description", ""),
		"organizer": event.get("organizerCalendarAddress", "").replace("mailto:", ""),
		"calendars": calendars,
		"locations": locations,
		"links": links,
		"alerts": alerts,
		"participants": participants,
		"created_utc": event["created"],
		"updated_utc": event["updated"],
		"free_busy_status": event.get("freeBusyStatus", "").upper(),
		"sequence": cint(event.get("sequence", 0)),
		"creation": parse_iso_datetime(event["created"]),
		"modified": parse_iso_datetime(event["updated"]),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Calendar Event":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
