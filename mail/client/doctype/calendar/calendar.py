# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from typing import Literal
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from mail.jmap import get_calendar_service
from mail.utils import parse_filters
from mail.utils.validation import has_permission_for_user


class Calendar(Document):
	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_calendar(
			self.user,
			self._name,
			self.color,
			self.description,
			self.sort_order,
			self.include_in_availability,
			self.time_zone,
			bool(self.subscribed),
			bool(self.visible),
			bool(self.default),
		)
		self.name = f"{self.user}|{self.id}"

	def load_from_db(self) -> "Calendar":
		user, id = self.name.split("|")
		calendar = get_calendar(user, id)
		return super(Document, self).__init__(calendar)

	def db_update(self) -> None:
		update_calendar(
			self.user,
			self.id,
			self._name,
			self.color,
			self.description,
			self.sort_order,
			self.include_in_availability,
			self.time_zone,
			bool(self.subscribed),
			bool(self.visible),
			bool(self.default),
		)
		self.reload()

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_calendars(user, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view calendars."), alert=True)
			return []

		calendars = fetch_calendars(user, limit=page_length)

		if not calendars:
			frappe.msgprint(_("No calendars found."), alert=True)

		return calendars

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


def _get_total_cache_key(user: str) -> str:
	"""Returns a cache key for total calendar count for the given user."""

	return f"{user}:calendars:total"


def validate_calendar_name_format(name: str) -> None:
	"Validates that the calendar name is in the format 'user|id'."

	parts = name.split("|")
	if len(parts) != 2:
		frappe.throw(_("Calendar name must be in the format 'user|id'."))


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes multiple calendars given their names."""

	if isinstance(names, str):
		names = json.loads(names)

	user_ids_map = {}
	for name in names:
		user, id = name.split("|")
		user_ids_map.setdefault(user, []).append(id)

	for user, ids in user_ids_map.items():
		delete_calendars(user, ids)

	frappe.msgprint(_("Calendars deleted successfully."), alert=True)


@frappe.whitelist()
def add_calendar(
	user: str,
	name: str,
	color: str | None = None,
	description: str | None = None,
	sort_order: int = 0,
	include_in_availability: Literal["All", "Attending", "None"] = "All",
	time_zone: str | None = None,
	subscribed: bool = True,
	visible: bool = True,
	default: bool = False,
) -> str:
	"""Adds a calendar for the given user with the specified parameters."""

	has_permission_for_user(user)

	creation_id = str(uuid7())
	calendar = {
		"creation_id": creation_id,
		"name": name,
		"color": color,
		"description": description,
		"sort_order": sort_order,
		"include_in_availability": include_in_availability.lower(),
		"time_zone": time_zone,
		"is_subscribed": subscribed,
		"is_visible": visible,
		"is_default": default,
	}

	service = get_calendar_service(user)
	response = service.create([calendar])

	title = _("Calendar Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_calendar(user: str, id: str) -> dict:
	"""Returns calendar details for the given name in the format 'user|id'."""

	has_permission_for_user(user)

	service = get_calendar_service(user)
	if calendars := service.get([id]):
		return format_calendar(user, calendars[0])

	frappe.throw(
		_("Calendar with ID {0} not found for user {1}").format(frappe.bold(id), frappe.bold(user)),
		title=_("Calendar Not Found"),
	)


@frappe.whitelist()
def update_calendar(
	user: str,
	id: str,
	name: str,
	color: str | None = None,
	description: str | None = None,
	sort_order: int = 0,
	include_in_availability: Literal["All", "Attending", "None"] = "All",
	time_zone: str | None = None,
	subscribed: bool = True,
	visible: bool = True,
	default: bool = False,
) -> None:
	"""Updates an existing calendar with the given parameters."""

	has_permission_for_user(user)

	calendar = {
		"id": id,
		"name": name,
		"color": color,
		"description": description,
		"sort_order": sort_order,
		"include_in_availability": include_in_availability.lower(),
		"time_zone": time_zone,
		"is_subscribed": subscribed,
		"is_visible": visible,
		"is_default": default,
	}

	service = get_calendar_service(user)
	response = service.update([calendar])

	title = _("Calendar Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_calendars(user: str, ids: list[str], remove_events: bool = True) -> None:
	"""Deletes calendars for the specified user and ID(s)."""

	has_permission_for_user(user)

	service = get_calendar_service(user)
	response = service.delete(ids, remove_events=remove_events)

	if response.get("notDestroyed"):
		error_messages = []
		for id, error in response["notDestroyed"].items():
			error_messages.append(f"{id}: {error['description']}")
		frappe.throw(
			_("Calendar Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
			title=_("Calendar Deletion Error"),
		)


@frappe.whitelist()
def fetch_calendars(user: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of calendars for the given user."""

	has_permission_for_user(user)

	service = get_calendar_service(user)
	calendars = service.get()
	formatted_calendars = [format_calendar(user, calendar) for calendar in calendars]
	frappe.cache.set_value(_get_total_cache_key(user), len(calendars), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_calendars[start:end]


def format_calendar(user: str, calendar: dict) -> dict:
	"""Formats calendar data for display."""

	share_with = []
	for pid, r in calendar.get("shareWith", {}).items():
		share_with.append(
			{
				"principal_id": pid,
				"may_read_free_busy": cint(bool(r.get("mayReadFreeBusy", False))),
				"may_read_items": cint(bool(r.get("mayReadItems", False))),
				"may_write_all": cint(bool(r.get("mayWriteAll", False))),
				"may_write_own": cint(bool(r.get("mayWriteOwn", False))),
				"may_update_private": cint(bool(r.get("mayUpdatePrivate", False))),
				"may_rsvp": cint(bool(r.get("mayRSVP", False))),
				"may_admin": cint(bool(r.get("mayAdmin", False))),
				"may_delete": cint(bool(r.get("mayDelete", False))),
			}
		)

	rights = calendar.get("myRights") or {}

	return {
		"name": f"{user}|{calendar['id']}",
		"user": user,
		"id": calendar["id"],
		"_name": calendar["name"],
		"description": calendar["description"],
		"subscribed": cint(bool(calendar["isSubscribed"])),
		"visible": cint(bool(calendar.get("isVisible"))),
		"default": cint(bool(calendar.get("isDefault"))),
		"color": calendar["color"],
		"sort_order": cint(calendar["sortOrder"]),
		"include_in_availability": calendar.get("includeInAvailability", "all").title(),
		"time_zone": calendar["timeZone"],
		"share_with": share_with,
		"may_read_free_busy": cint(bool(rights.get("mayReadFreeBusy", False))),
		"may_read_items": cint(bool(rights.get("mayReadItems", False))),
		"may_write_all": cint(bool(rights.get("mayWriteAll", False))),
		"may_write_own": cint(bool(rights.get("mayWriteOwn", False))),
		"may_update_private": cint(bool(rights.get("mayUpdatePrivate", False))),
		"may_rsvp": cint(bool(rights.get("mayRSVP", False))),
		"may_admin": cint(bool(rights.get("mayAdmin", False))),
		"may_delete": cint(bool(rights.get("mayDelete", False))),
		"creation": today(),
		"modified": today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Calendar":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
