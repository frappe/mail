# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from typing import Literal
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from mail.jmap import get_calendar_service, parse_account
from mail.utils import parse_filters
from mail.utils.validation import has_permission_for_user


class Calendar(Document):
	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_calendar(
			self.account,
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
		self.name = f"{self.account}|{self.id}"

	def load_from_db(self) -> "Calendar":
		account, id = self.name.split("|")
		calendar = get_calendar(account, id)
		return super(Document, self).__init__(calendar)

	def db_update(self) -> None:
		update_calendar(
			self.account,
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
		account, id = self.name.split("|")
		delete_calendars(account, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		account = filters.get("account")

		if not account:
			frappe.msgprint(_("Please select an account to view calendars."), alert=True)
			return []

		calendars = fetch_calendars(account, limit=page_length)

		if not calendars:
			frappe.msgprint(_("No calendars found."), alert=True)

		return calendars

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		account = filters.get("account")

		if account:
			user, _account_id = parse_account(account)

			if has_permission_for_user(user, raise_exception=False):
				return cint(frappe.cache.get_value(_get_total_cache_key(account)))

		return 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}


def _get_total_cache_key(account: str) -> str:
	"""Returns a cache key for total calendar count for the given account."""

	return f"{account}:calendars:total"


def validate_calendar_name_format(name: str) -> None:
	"Validates that the calendar name is in the format 'account|id'."

	parts = name.split("|")
	if len(parts) != 2:
		frappe.throw(_("Calendar name must be in the format 'account|id'."))


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes multiple calendars given their names."""

	if isinstance(names, str):
		names = json.loads(names)

	account_ids_map = {}
	for name in names:
		account, id = name.split("|")
		account_ids_map.setdefault(account, []).append(id)

	for account, ids in account_ids_map.items():
		delete_calendars(account, ids)

	frappe.msgprint(_("Calendars deleted successfully."), alert=True)


@frappe.whitelist()
def add_calendar(
	account: str,
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
	"""Adds a calendar for the given account with the specified parameters."""

	user, _account_id = parse_account(account)
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

	service = get_calendar_service(account)
	response = service.create([calendar])

	title = _("Calendar Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_calendar(account: str, id: str) -> dict:
	"""Returns calendar details for the given name in the format 'account|id'."""

	user, _account_id = parse_account(account)
	has_permission_for_user(user)

	service = get_calendar_service(account)
	if calendars := service.get([id]):
		return format_calendar(account, calendars[0])

	frappe.throw(
		_("Calendar with ID {0} not found for account {1}").format(frappe.bold(id), frappe.bold(account)),
		title=_("Calendar Not Found"),
	)


@frappe.whitelist()
def update_calendar(
	account: str,
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

	user, _account_id = parse_account(account)
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

	service = get_calendar_service(account)
	response = service.update([calendar])

	title = _("Calendar Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_calendars(account: str, ids: list[str], remove_events: bool = True) -> None:
	"""Deletes calendars for the specified account and ID(s)."""

	user, _account_id = parse_account(account)
	has_permission_for_user(user)

	service = get_calendar_service(account)
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
def fetch_calendars(account: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of calendars for the given account."""

	user, _account_id = parse_account(account)
	has_permission_for_user(user)

	service = get_calendar_service(account)
	calendars = service.get()
	formatted_calendars = [format_calendar(account, calendar) for calendar in calendars]
	frappe.cache.set_value(_get_total_cache_key(account), len(calendars), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_calendars[start:end]


def format_calendar(account: str, calendar: dict) -> dict:
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
		"name": f"{account}|{calendar['id']}",
		"account": account,
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

	doc_user, _account_id = parse_account(doc.account)

	return has_permission_for_user(doc_user, raise_exception=False)
