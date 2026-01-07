# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from typing import Literal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint
from uuid_utils import uuid7

from mail.client.doctype.calendar.calendar import validate_calendar_name_format
from mail.jmap import get_jmap_client
from mail.utils import parse_filters
from mail.utils.cache import get_root_domain_name
from mail.utils.dt import parse_iso_datetime
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
			organizer=self.organizer,
			description=self.description,
			recurrence_rule=self.formatted_recurrence_rule,
			locations=self.formatted_locations,
			alerts=self.formatted_alerts,
			participants=self.formatted_participants,
			show_without_time=bool(self.show_without_time),
			use_default_alerts=bool(self.use_default_alerts),
			send_scheduling_messages=bool(self.send_scheduling_messages),
		)
		self.name = f"{self.user}|{self.id}"
		self.reload()

	def load_from_db(self) -> "CalendarEvent":
		user, id = self.name.split("|")
		event = get_calendar_event(user, id)
		return super(Document, self).__init__(event)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_calendar_event(user, id)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view calendar events."), alert=True)
			return []

		events = fetch_calendar_events(user, limit=page_length)

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
		self.validate_calendars()

	def validate_calendars(self) -> None:
		"""Validates that at least one calendar is associated with the event."""

		if not self.calendars:
			frappe.throw(_("A event must belong to at least one calendar."))

		for c in self.calendars:
			validate_calendar_name_format(c.calendar)
			_user, calendar_id = c.calendar.split("|")
			c.calendar_id = calendar_id


def _get_total_cache_key(user: str) -> str:
	"""Returns a cache key for total calendar events count for the given user."""

	return f"{user}:calendar_events:total"


@frappe.whitelist()
def add_calendar_event(
	user: str,
	calendar_ids: list[str],
	status: Literal["Tentative", "Confirmed", "Cancelled"],
	title: str,
	start: str,
	duration: str,
	time_zone: str,
	organizer: str | None = None,
	description: str | None = None,
	recurrence_rule: dict | None = None,
	locations: list[dict] | None = None,
	alerts: list[dict] | None = None,
	participants: list[dict] | None = None,
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
		organizer=organizer,
		description=description,
		recurrence_rule=recurrence_rule,
		locations=locations,
		alerts=alerts,
		participants=participants,
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
def get_calendar_event(user: str, id: str) -> dict:
	"""Returns calendar event details for the given name in the format 'user|id'."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	if events := client.calendar_event_get([id]):
		calendar_map = {c["id"]: c["_name"] for c in client.calendars}
		return format_calendar_event(user, calendar_map, events[0])

	frappe.throw(
		_("Calendar Event with ID {0} not found for user {1}").format(frappe.bold(id), frappe.bold(user)),
		title=_("Calendar Event Not Found"),
	)


@frappe.whitelist()
def update_calendar_event() -> None:
	pass


@frappe.whitelist()
def delete_calendar_event(user: str, id: str) -> None:
	"""Deletes a calendar event for the given user by its ID."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	response = client.calendar_event_delete([id])

	if response.get("notDestroyed"):
		frappe.throw(_(response["notDestroyed"][id]["description"]), title=_("Calendar Event Deletion Error"))


@frappe.whitelist()
def fetch_calendar_events(user: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of calendar events for the given user."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	events = client.calendar_event_get()
	calendar_map = {c["id"]: c["_name"] for c in client.calendars}
	formatted_events = [format_calendar_event(user, calendar_map, event) for event in events]
	frappe.cache.set_value(_get_total_cache_key(user), len(events), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_events[start:end]


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
		"recurrence_rule": json.dumps(event.get("recurrenceRule", {}), indent=2),
		"description": event.get("description", ""),
		"organizer": event.get("organizerCalendarAddress", "").replace("mailto:", ""),
		"calendars": calendars,
		"locations": locations,
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
