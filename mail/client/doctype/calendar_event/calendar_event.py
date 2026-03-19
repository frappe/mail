# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json
from functools import cached_property
from typing import Literal
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.client.doctype.calendar.calendar import validate_calendar_name_format
from mail.jmap import get_calendar_event_service, get_identity_service
from mail.utils import parse_filters
from mail.utils.cache import get_root_domain_name
from mail.utils.dt import convert_to_utc, parse_iso_datetime, utcnow
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
					"comment": p.comment,
				}
				for p in self.participants
			]

	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_calendar_event(
			user=self.user,
			organizer=self.organizer,
			calendar_ids=self.calendar_ids,
			status=self.status,
			draft=bool(self.draft),
			title=self.title,
			start=self.start,
			duration=self.duration,
			time_zone=self.time_zone,
			recurrence_rule=self.formatted_recurrence_rule,
			show_without_time=bool(self.show_without_time),
			privacy=self.privacy,
			free_busy_status=self.free_busy_status,
			description=self.description,
			locations=self.formatted_locations,
			links=self.formatted_links,
			participants=self.formatted_participants,
			alerts=self.formatted_alerts,
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
		update_calendar_event(
			user=self.user,
			id=self.id,
			uid=self.uid,
			organizer=self.organizer,
			calendar_ids=self.calendar_ids,
			status=self.status,
			draft=bool(self.draft),
			title=self.title,
			start=self.start,
			duration=self.duration,
			time_zone=self.time_zone,
			recurrence_rule=self.formatted_recurrence_rule,
			show_without_time=bool(self.show_without_time),
			privacy=self.privacy,
			free_busy_status=self.free_busy_status,
			description=self.description,
			locations=self.formatted_locations,
			links=self.formatted_links,
			participants=self.formatted_participants,
			alerts=self.formatted_alerts,
			use_default_alerts=bool(self.use_default_alerts),
			send_scheduling_messages=bool(self.send_scheduling_messages),
		)
		self.reload()

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_calendar_events(user, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)

		title = filters.get("title")
		calendar = filters.get("calendar")
		user = filters.get("user") or frappe.session.user
		after = filters.get("after") and convert_to_utc(filters.get("after"), naive=True).strftime(
			"%Y-%m-%dT%H:%M:%SZ"
		)
		before = filters.get("before") and convert_to_utc(filters.get("before"), naive=True).strftime(
			"%Y-%m-%dT%H:%M:%SZ"
		)

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view calendar events."), alert=True)
			return []

		filter = {}
		if title:
			filter["title"] = title
		if calendar:
			validate_calendar_name_format(calendar)
			filter["inCalendar"] = calendar.split("|")[1]
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

		if not self.draft:
			if not self.start:
				frappe.throw(_("Start time is required for non-draft events."))
			if not self.duration:
				frappe.throw(_("Duration is required for non-draft events."))

	def validate_calendars(self) -> None:
		"""Validates that at least one calendar is associated with the event."""

		for c in self.calendars or []:
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
	organizer: str | None = None,
	calendar_ids: list[str] | None = None,
	status: Literal["Tentative", "Confirmed", "Cancelled"] = "Confirmed",
	draft: bool = False,
	title: str | None = None,
	start: str | None = None,
	duration: str | None = None,
	time_zone: str | None = None,
	recurrence_rule: dict | None = None,
	show_without_time: bool = False,
	privacy: str | None = None,
	free_busy_status: str | None = None,
	description: str | None = None,
	locations: list[dict] | None = None,
	links: list[dict] | None = None,
	participants: list[dict] | None = None,
	alerts: list[dict] | None = None,
	use_default_alerts: bool = False,
	send_scheduling_messages: bool = False,
) -> str:
	"""Adds a calendar event for the given user and returns the event ID."""

	has_permission_for_user(user)

	uid = f"{uuid7().hex}@{get_root_domain_name()}"
	creation_id = str(uuid7())
	event = {
		"creation_id": creation_id,
		"uid": uid,
		"organizer": organizer,
		"calendar_ids": calendar_ids,
		"status": status.lower(),
		"draft": draft,
		"title": title,
		"start": start,
		"duration": duration,
		"time_zone": time_zone,
		"recurrence_rule": recurrence_rule,
		"show_without_time": show_without_time,
		"privacy": privacy.lower() if privacy else None,
		"free_busy_status": free_busy_status.lower() if free_busy_status else None,
		"description": description,
		"locations": locations,
		"links": links,
		"participants": participants,
		"alerts": alerts,
		"use_default_alerts": use_default_alerts,
	}

	service = get_calendar_event_service(user)
	response = service.create([event], send_scheduling_messages=send_scheduling_messages)

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

	service = get_calendar_event_service(user)
	data = service.query(filter, position, limit, sort, time_zone, expand_recurrences)

	ids = data.get("ids", [])
	total = data.get("total", 0)

	calendar_events.extend(get_calendar_events(user, ids))

	return calendar_events[:limit], total


@frappe.whitelist()
def get_calendar_events(user: str, ids: list[str]) -> list[dict]:
	"""Returns a list of calendar events for the specified user and IDs."""

	has_permission_for_user(user)

	service = get_calendar_event_service(user)
	calendar_map = {c["id"]: c["name"] for c in service.calendars}

	events = {}
	for event in service.get(ids):
		event = format_calendar_event(user, calendar_map, event)
		events[event["id"]] = event

	return [events[id] for id in ids if id in events]


@frappe.whitelist()
def get_calendar_event_by_uid(user: str, uid: str) -> dict:
	"""Returns a calendar event for the specified user and event UID."""

	has_permission_for_user(user)

	service = get_calendar_event_service(user)
	calendar_map = {c["id"]: c["name"] for c in service.calendars}

	event = service.get_by_uid(uid)
	if event:
		return format_calendar_event(user, calendar_map, event)

	frappe.throw(
		_("Calendar Event with UID {0} not found for user {1}.").format(frappe.bold(uid), frappe.bold(user)),
		title=_("Calendar Event Not Found"),
	)


@frappe.whitelist()
def update_calendar_event(
	user: str,
	id: str,
	uid: str | None = None,
	organizer: str | None = None,
	calendar_ids: list[str] | None = None,
	status: Literal["Tentative", "Confirmed", "Cancelled"] = "Confirmed",
	draft: bool = False,
	title: str | None = None,
	start: str | None = None,
	duration: str | None = None,
	time_zone: str | None = None,
	recurrence_rule: dict | None = None,
	show_without_time: bool = False,
	privacy: str | None = None,
	free_busy_status: str | None = None,
	description: str | None = None,
	locations: list[dict] | None = None,
	links: list[dict] | None = None,
	participants: list[dict] | None = None,
	alerts: list[dict] | None = None,
	use_default_alerts: bool = False,
	send_scheduling_messages: bool = False,
) -> None:
	"""Updates a calendar event for the given user and event ID."""

	has_permission_for_user(user)

	event = {
		"id": id,
		"uid": uid,
		"organizer": organizer,
		"calendar_ids": calendar_ids,
		"status": status.lower(),
		"draft": draft,
		"title": title,
		"start": start,
		"duration": duration,
		"time_zone": time_zone,
		"recurrence_rule": recurrence_rule,
		"show_without_time": show_without_time,
		"privacy": privacy.lower() if privacy else None,
		"free_busy_status": free_busy_status.lower() if free_busy_status else None,
		"description": description,
		"locations": locations,
		"links": links,
		"participants": participants,
		"alerts": alerts,
		"use_default_alerts": use_default_alerts,
	}

	service = get_calendar_event_service(user)
	response = service.update([event], send_scheduling_messages=send_scheduling_messages)

	title = _("Calendar Event Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def update_calendar_event_instance(
	user: str,
	uid: str,
	recurrence_id: str,
	patch: dict,
	send_scheduling_messages: bool = False,
) -> None:
	"""Updates a specific instance of a recurring calendar event based on its UID and recurrence ID."""

	has_permission_for_user(user)

	service = get_calendar_event_service(user)
	response = service.update_instance(
		uid, recurrence_id, patch, send_scheduling_messages=send_scheduling_messages
	)

	title = _("Calendar Event Instance Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_calendar_events(user: str, ids: list[str]) -> None:
	"""Deletes a calendar event for the given user by its ID."""

	has_permission_for_user(user)

	service = get_calendar_event_service(user)
	response = service.delete(ids)

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
def delete_calendar_event_instance(user: str, uid: str, recurrence_id: str) -> None:
	"""Deletes a specific instance of a recurring calendar event based on its UID and recurrence ID."""

	has_permission_for_user(user)

	service = get_calendar_event_service(user)
	response = service.delete_instance(uid, recurrence_id)

	if response.get("notDestroyed"):
		error_messages = []
		for id, error in response["notDestroyed"].items():
			error_messages.append(f"{id}: {error['description']}")
		frappe.throw(
			_("Calendar Event Instance Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
			title=_("Calendar Event Instance Deletion Error"),
		)


@frappe.whitelist()
def parse_ics(user: str, ics_data: bytes | str) -> list[dict]:
	"""Parses ICS data and returns calendar event details."""

	has_permission_for_user(user)

	service = get_calendar_event_service(user)
	blob_id = service.upload_blob(ics_data, content_type="text/calendar; charset=utf-8").get("blobId")

	if not blob_id:
		frappe.throw(_("Failed to upload ICS data."), title=_("ICS Upload Error"))

	response = service.parse([blob_id])

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
		p["roles"] = p.get("roles") or {}
		roles = {r.lower(): v for r, v in p.get("roles").items()}
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
				"comment": p.get("comment", ""),
			}
		)

	organizer = (
		event.get("organizerCalendarAddress")
		and event["organizerCalendarAddress"].lower().replace("mailto:", "")
		or ""
	)

	created = event.get("created")
	updated = event.get("updated")
	created_utc = created or updated or utcnow()
	updated_utc = updated or created or utcnow()

	return {
		"user": user,
		"name": f"{user}|{event['id']}",
		"id": event["id"],
		"uid": event["uid"],
		"recurrence_id": event.get("recurrenceId"),
		"organizer": organizer,
		"calendars": calendars,
		"status": event.get("status") and event["status"].title() or "Confirmed",
		"draft": cint(event.get("isDraft") or False),
		"title": event.get("title") or "",
		"start": event.get("start") or "",
		"duration": event.get("duration") or "",
		"time_zone": event.get("timeZone") or "",
		"recurrence_id_time_zone": event.get("recurrenceIdTimeZone") or "",
		"recurrence_rule": json.dumps(event.get("recurrenceRule", {}), indent=2),
		"show_without_time": cint(event.get("showWithoutTime") or False),
		"privacy": event.get("privacy") and event["privacy"].title() or "",
		"free_busy_status": event.get("freeBusyStatus") and event["freeBusyStatus"].title() or "",
		"description": event.get("description") or "",
		"locations": locations,
		"links": links,
		"participants": participants,
		"alerts": alerts,
		"use_default_alerts": cint(event.get("useDefaultAlerts") or False),
		"created_utc": created_utc,
		"updated_utc": updated_utc,
		"origin": event.get("isOrigin") or False,
		"may_invite_self": cint(event.get("mayInviteSelf") or False),
		"may_invite_others": cint(event.get("mayInviteOthers") or False),
		"hide_attendees": cint(event.get("hideAttendees") or False),
		"creation": parse_iso_datetime(created_utc),
		"modified": parse_iso_datetime(updated_utc),
		"sequence": cint(event.get("sequence") or False),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Calendar Event":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
