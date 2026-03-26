from typing import ClassVar
from uuid import uuid7

from mail.jmap.services.calendars.calendar import CalendarService
from mail.jmap.services.calendars.calendars import CalendarsService
from mail.jmap.services.calendars.participant_identity import ParticipantIdentityService
from mail.utils.dt import utcnow


class CalendarEventService(CalendarsService):
	"""Service for handling calendar event-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "CalendarEvent"

	def create(self, events: list[dict], send_scheduling_messages: bool = False) -> dict:
		"""
		Public method to create calendar events, handling batching if the number of events exceeds the server's maximum allowed in a single 'set' call.
		If send_scheduling_messages is True, includes the sendSchedulingMessages flag in the request payload to indicate that scheduling messages should be sent for the created events.
		"""

		result = {"created": {}, "notCreated": {}}
		for batch in self.create_batches(events, self.max_objects_in_set):
			payload = {}
			for event in batch:
				timestamp = utcnow()

				calendar_ids = event.get("calendar_ids")
				if not calendar_ids:
					calendar_ids = [
						CalendarService(self.user, self.connection).get_default(raise_exception=True)
					]

				organizer = event.get("organizer")
				if not organizer:
					organizer = ParticipantIdentityService(self.user, self.connection).get_default(
						raise_exception=True
					)

				organizer = organizer.lower()
				if not organizer.startswith("mailto:"):
					organizer = f"mailto:{organizer}"

				payload[event["creation_id"]] = {
					"@type": "Event",
					"uid": event["uid"],
					"organizerCalendarAddress": organizer,
					"calendarIds": {id: True for id in calendar_ids},
					"status": event.get("status"),
					"isDraft": bool(event.get("is_draft") or False),
					"title": event.get("title"),
					"start": event.get("start"),
					"duration": event.get("duration"),
					"timeZone": event.get("time_zone"),
					"recurrenceRule": event.get("recurrence_rule") or None,
					"showWithoutTime": bool(event.get("show_without_time") or False),
					"privacy": event.get("privacy"),
					"freeBusyStatus": event.get("free_busy_status"),
					"description": event.get("description"),
					"locations": self._get_locations_map(event.get("locations")),
					"links": self._get_links_map(event.get("links")),
					"participants": self._get_participants_map(event.get("participants")),
					"alerts": self._get_alerts_map(event.get("alerts")),
					"useDefaultAlerts": bool(event.get("use_default_alerts") or False),
					"created": timestamp,
					"updated": timestamp,
				}

			response = self._create(payload, sendSchedulingMessages=send_scheduling_messages)

			if method_responses := response.get("methodResponses"):
				result["created"].update(method_responses[0][1].get("created", {}))
				if not_created := method_responses[0][1].get("notCreated", {}):
					result["notCreated"].update(not_created)

		return result

	def get(self, ids: list[str] | None = None) -> list[dict]:
		"""Public method to get calendar events, handling batching if a list of ids is provided."""

		results = []
		if ids:
			for batch in self.create_batches(ids, self.max_objects_in_get):
				response = self._get(batch)

				if method_responses := response.get("methodResponses"):
					results.extend(method_responses[0][1].get("list", []))
		else:
			response = self._get()
			if method_responses := response.get("methodResponses"):
				results.extend(method_responses[0][1].get("list", []))

		return results

	def update(self, events: list[dict], send_scheduling_messages: bool = False) -> dict:
		"""
		Public method to update calendar events, handling batching if the number of events exceeds the server's maximum allowed in a single 'set' call.
		If send_scheduling_messages is True, includes the sendSchedulingMessages flag in the request payload to indicate that scheduling messages should be sent for the updated events.
		"""

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(events, self.max_objects_in_set):
			payload = {}
			for event in batch:
				calendar_ids = event.get("calendar_ids")
				if not calendar_ids:
					calendar_ids = [
						CalendarService(self.user, self.connection).get_default(raise_exception=True)
					]

				payload[event["id"]] = {
					"@type": "Event",
					"calendarIds": {id: True for id in calendar_ids},
					"privacy": event.get("privacy"),
					"freeBusyStatus": event.get("free_busy_status"),
					"alerts": self._get_alerts_map(event.get("alerts")),
				}

				organizer = event.get("organizer")

				if organizer:
					organizer = organizer.lower()

					if not organizer.startswith("mailto:"):
						organizer = f"mailto:{organizer}"

				payload[event["id"]].update(
					{
						"uid": event["uid"],
						"organizerCalendarAddress": organizer,
						"status": event.get("status"),
						"isDraft": bool(event.get("is_draft") or False),
						"title": event.get("title"),
						"start": event.get("start"),
						"duration": event.get("duration"),
						"timeZone": event.get("time_zone"),
						"recurrenceRule": event.get("recurrence_rule") or None,
						"showWithoutTime": bool(event.get("show_without_time") or False),
						"description": event.get("description"),
						"locations": self._get_locations_map(event.get("locations")),
						"links": self._get_links_map(event.get("links")),
						"participants": self._get_participants_map(event.get("participants")),
						"useDefaultAlerts": bool(event.get("use_default_alerts") or False),
						"updated": utcnow(),
					}
				)

			response = self._update(payload, sendSchedulingMessages=send_scheduling_messages)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	def delete(self, ids: list[str]) -> dict:
		"""Public method to delete calendar events, handling batching if the number of events exceeds the server's maximum allowed in a single 'set' call."""

		result = {"destroyed": [], "notDestroyed": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			response = self._delete(batch)

			if method_responses := response.get("methodResponses"):
				result["destroyed"].extend(method_responses[0][1].get("destroyed", []))
				if not_destroyed := method_responses[0][1].get("notDestroyed", {}):
					result["notDestroyed"].update(not_destroyed)

		return result

	def query(
		self,
		filter: dict | None = None,
		position: int = 0,
		limit: int = 50,
		sort: list[dict] | None = None,
		time_zone: str | None = None,
		expand_recurrences: bool = False,
	) -> dict:
		"""Public method to query calendar events, handling batching if the number of results exceeds the server's maximum allowed in a single 'query' call."""

		ids = []
		total = None
		batch_size = min(limit, self.max_objects_in_get)
		sort = sort or [{"property": "start", "isAscending": True}]

		while len(ids) < limit:
			response = self._query(
				filter,
				position,
				batch_size,
				sort,
				calculate_total=total is None,
				timeZone=time_zone,
				expandRecurrences=expand_recurrences,
			)

			if method_responses := response.get("methodResponses"):
				query_response = method_responses[0][1]

				ids.extend(query_response.get("ids", []))

				if total is None:
					total = query_response.get("total", 0)

				if not query_response.get("hasMoreItems", False):
					break

				position += batch_size

		return {"ids": ids[:limit], "total": total}

	def changes(self, since_state: str) -> dict:
		"""Public method to get calendar event changes since a given state."""

		response = self._changes(since_state)

		if method_responses := response.get("methodResponses"):
			return method_responses[0][1]

		return {}

	def parse(self, blob_ids: list[str]) -> dict:
		"""Public method to parse calendar event blobs, handling batching if the number of blob ids exceeds the server's maximum allowed in a single 'get' call."""

		result = {"parsed": {}, "notFound": {}, "notParsable": {}}
		for batch in self.create_batches(blob_ids, self.max_objects_in_get):
			response = self._call(
				self.capabilities,
				[
					[
						f"{self.type}/parse",
						{
							"accountId": self.primary_account_id,
							"blobIds": batch,
						},
						"0",
					]
				],
			)

			if method_responses := response.get("methodResponses"):
				result["parsed"].update(method_responses[0][1].get("parsed", {}))
				if not_found := method_responses[0][1].get("notFound", {}):
					result["notFound"].update(not_found)
				if not_parsable := method_responses[0][1].get("notParsable", {}):
					result["notParsable"].update(not_parsable)

		return result

	def get_master_ids(self, uids: list[str]) -> list[str]:
		"""Public method to get master event IDs for a list of UIDs."""

		return self.query(
			{
				"operator": "OR",
				"conditions": [{"uid": uid} for uid in uids],
			},
			position=0,
			limit=len(uids),
			expand_recurrences=False,
		).get("ids", [])

	def update_instance(
		self, id: str, recurrence_id: str, patch: dict, send_scheduling_messages: bool = False
	) -> dict:
		"""Public method to update a specific instance of a recurring calendar event based on its ID and recurrence ID by applying the provided patch to the master event's recurrence overrides."""

		if not id or not recurrence_id:
			raise ValueError("Both 'id' and 'recurrence_id' are required.")
		if not patch:
			raise ValueError("Patch data is required to update an instance.")

		events = self.get([id])
		if not events:
			raise ValueError(f"Event with id '{id}' not found.")

		event = events[0]
		recurrence_overrides = event.get("recurrenceOverrides", {}) or {}

		def _mailto(value: str) -> str:
			value = value.lower()
			return value if value.startswith("mailto:") else f"mailto:{value}"

		FIELD_MAP = {
			"calendar_ids": ("calendarIds", lambda v: {i: True for i in v}),
			"privacy": ("privacy", None),
			"free_busy_status": ("freeBusyStatus", None),
			"alerts": ("alerts", self._get_alerts_map),
			"organizer": ("organizerCalendarAddress", _mailto),
			"uid": ("uid", None),
			"status": ("status", None),
			"title": ("title", None),
			"start": ("start", None),
			"duration": ("duration", None),
			"time_zone": ("timeZone", None),
			"recurrence_rule": ("recurrenceRule", None),
			"show_without_time": ("showWithoutTime", lambda v: bool(v)),
			"description": ("description", None),
			"locations": ("locations", self._get_locations_map),
			"links": ("links", self._get_links_map),
			"participants": ("participants", self._get_participants_map),
			"use_default_alerts": ("useDefaultAlerts", lambda v: bool(v)),
		}

		out = {}
		for key, (target, transform) in FIELD_MAP.items():
			if key in patch:
				value = patch[key]
				out[target] = transform(value) if transform else value

		payload = {id: {}}

		if recurrence_id in recurrence_overrides:
			payload[id].update({f"recurrenceOverrides/{recurrence_id}/{k}": v for k, v in out.items()})
		else:
			recurrence_overrides[recurrence_id] = out
			payload = {id: {"recurrenceOverrides": recurrence_overrides}}

		payload[id]["updated"] = utcnow()

		response = self._update(payload, sendSchedulingMessages=send_scheduling_messages)

		result = {"updated": [], "notUpdated": {}}
		if method_responses := response.get("methodResponses"):
			result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
			if not_updated := method_responses[0][1].get("notUpdated", {}):
				result["notUpdated"].update(not_updated)

		return result

	def delete_instance(self, id: str, recurrence_id: str) -> dict:
		"""Public method to delete a specific instance of a recurring calendar event based on its ID and recurrence ID by marking it as excluded in the master event's recurrence overrides."""

		if not id or not recurrence_id:
			raise ValueError("Both 'id' and 'recurrence_id' are required.")

		events = self.get([id])
		if not events:
			raise ValueError(f"Event with id '{id}' not found.")

		event = events[0]
		recurrence_overrides = event.get("recurrenceOverrides", {}) or {}
		recurrence_overrides.setdefault(recurrence_id, {}).update({"excluded": True})

		response = self._update({id: {"recurrenceOverrides": recurrence_overrides, "updated": utcnow()}})

		result = {"updated": [], "notUpdated": {}}
		if method_responses := response.get("methodResponses"):
			result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
			if not_updated := method_responses[0][1].get("notUpdated", {}):
				result["notUpdated"].update(not_updated)

		return result

	@staticmethod
	def _get_locations_map(locations: list[dict] | None = None) -> dict[str, dict] | None:
		if locations:
			locations_map = {}
			for location in locations:
				uid = location.get("uid") or str(uuid7())
				locations_map[uid] = {
					"@type": "Location",
					"name": location.get("name"),
				}

			return locations_map

	@staticmethod
	def _get_links_map(links: list[dict] | None = None) -> dict[str, dict] | None:
		if links:
			links_map = {}
			for link in links:
				uid = link.get("uid") or str(uuid7())
				links_map[uid] = {
					"@type": "Link",
					"href": link.get("href"),
					"contentType": link.get("content_type"),
				}

			return links_map

	@staticmethod
	def _get_alerts_map(alerts: list[dict] | None = None) -> dict[str, dict] | None:
		if alerts:
			alerts_map = {}
			for alert in alerts:
				if alert["type"] == "OffsetTrigger":
					trigger = {
						"@type": "OffsetTrigger",
						"relativeTo": alert["relative_to"].lower(),
						"offset": alert["offset"].upper(),
					}
				elif alert["type"] == "AbsoluteTrigger":
					trigger = {
						"@type": "AbsoluteTrigger",
						"when": alert["when"].upper(),
					}
				else:
					continue

				uid = alert.get("uid") or str(uuid7())
				alerts_map[uid] = {
					"@type": "Alert",
					"action": alert["action"].lower(),
					"trigger": trigger,
				}

			return alerts_map

	@staticmethod
	def _get_participants_map(participants: list[dict] | None = None) -> dict[str, dict] | None:
		"""Helper method to construct the 'participants' property map for a calendar event based on the provided list of participant dictionaries."""

		if participants:
			participants_map = {}
			participants_emails = []
			for participant in participants:
				email = participant["email"].lower()
				uid = participant.get("uid") or str(uuid7())
				expect_reply = participant.get("expect_reply", False)
				calendar_address = f"mailto:{email}" if email else None

				if expect_reply:
					send_to = (
						participant.get("send_to") or {"imip": calendar_address} if calendar_address else None
					)
					schedule_id = participant.get("schedule_id") or calendar_address
				else:
					send_to = None
					schedule_id = None

				participants_map[uid] = {
					"@type": "Participant",
					"name": participant.get("name") or email,
					"sendTo": send_to,
					"scheduleId": schedule_id,
					"calendarAddress": calendar_address,
					"kind": participant.get("kind", "").lower() or None,
					"description": participant.get("description") or None,
					"roles": participant.get("roles") or None,
					"participationStatus": participant.get("participation_status", "").lower() or None,
					"expectReply": expect_reply,
					"comment": participant.get("comment") or None,
				}
				participants_emails.append(email)

			return participants_map
