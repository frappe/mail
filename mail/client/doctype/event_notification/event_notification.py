# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.jmap import get_calendar_event_notification_service, parse_account
from mail.utils import parse_filters
from mail.utils.dt import parse_iso_datetime
from mail.utils.validation import has_permission_for_user


class EventNotification(Document):
	def db_insert(self, *args, **kwargs) -> None:
		frappe.throw(
			_("Event Notification are only created by the server, users cannot create them directly.")
		)

	def load_from_db(self) -> "EventNotification":
		account, id = self.name.split("|")
		if notifications := get_event_notifications(account, [id]):
			return super(Document, self).__init__(notifications[0])

		frappe.throw(
			_("Event Notification with ID {0} not found in account {1}.").format(
				frappe.bold(id), frappe.bold(account)
			),
			title=_("Event Notification Not Found"),
		)

	def db_update(self) -> None:
		frappe.throw(_("Event Notification cannot be updated by the user."))

	def delete(self) -> None:
		account, id = self.name.split("|")
		delete_event_notifications(account, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		account = filters.get("account")

		if not account:
			frappe.msgprint(_("Please select an account to view event notifications."), alert=True)
			return []

		filter = {}
		limit = cint(kwargs.get("start")) + page_length
		notifications, total = fetch_event_notifications(account, filter, limit=limit)
		frappe.cache.set_value(_get_total_cache_key(account), total, expires_in_sec=600)

		if not notifications:
			frappe.msgprint(_("No event notifications found."), alert=True)

		return notifications

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
	"""Returns a cache key for total event notifications count for the given account."""

	return f"{account}:event_notifications:total"


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes multiple event notifications given their names."""

	if isinstance(names, str):
		names = json.loads(names)

	account_ids_map = {}
	for name in names:
		account, id = name.split("|")
		account_ids_map.setdefault(account, []).append(id)

	for account, ids in account_ids_map.items():
		delete_event_notifications(account, ids)

	frappe.msgprint(_("Event Notifications deleted successfully."), alert=True)


@frappe.whitelist()
def fetch_event_notifications(
	account: str,
	filter: dict | None = None,
	position: int = 0,
	limit: int = 50,
	sort: list[dict] | None = None,
) -> tuple[list[dict], int]:
	"""Returns a list of event notifications and total count based on the provided filter."""

	user, _account_id = parse_account(account)
	has_permission_for_user(user)

	notifications = []

	service = get_calendar_event_notification_service(account)
	data = service.query(filter, position, limit, sort)

	ids = data.get("ids", [])
	total = data.get("total", 0)

	notifications.extend(get_event_notifications(account, ids))

	return notifications[:limit], total


@frappe.whitelist()
def get_event_notifications(account: str, ids: list[str]) -> list[dict]:
	"""Returns a list of event notifications for the specified account and IDs."""

	user, _account_id = parse_account(account)
	has_permission_for_user(user)

	service = get_calendar_event_notification_service(account)

	notifications = {}
	for notification in service.get(ids):
		notification = format_event_notification(account, notification)
		notifications[notification["id"]] = notification

	return [notifications[id] for id in ids if id in notifications]


@frappe.whitelist()
def delete_event_notifications(account: str, ids: list[str]) -> None:
	"""Deletes event notifications for the specified account and ID(s)."""

	user, _account_id = parse_account(account)
	has_permission_for_user(user)

	service = get_calendar_event_notification_service(account)
	response = service.delete(ids)

	if response.get("notDestroyed"):
		error_messages = []
		for id, error in response["notDestroyed"].items():
			error_messages.append(f"{id}: {error['description']}")
		frappe.throw(
			_("Event Notification Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
			title=_("Event Notification Deletion Error"),
		)


def format_event_notification(account: str, notification: dict) -> dict:
	"""Formats event notification data for display."""

	calendar_event_id = notification.get("calendarEventId", "")
	calendar_event = f"{account}|{calendar_event_id}" if calendar_event_id else None
	changed_by = notification.get("changedBy", {})
	event = json.dumps(notification.get("event", {}), indent=2)
	event_patch = json.dumps(notification.get("eventPatch", {}), indent=2)

	return {
		"name": f"{account}|{notification['id']}",
		"account": account,
		"id": notification["id"],
		"draft": notification.get("isDraft", False),
		"type": notification.get("type", "").title(),
		"created_utc": notification["created"],
		"comment": notification.get("comment", ""),
		"calendar_event": calendar_event,
		"calendar_event_id": calendar_event_id,
		"changed_by_name": changed_by.get("name"),
		"changed_by_email": changed_by.get("email"),
		"changed_by_principal_id": changed_by.get("principalId"),
		"changed_by_schedule_id": changed_by.get("scheduleId"),
		"event": event,
		"event_patch": event_patch,
		"creation": parse_iso_datetime(notification["created"]),
		"modified": parse_iso_datetime(notification["created"]),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Event Notification":
		return False

	doc_user, _account_id = parse_account(doc.account)

	return has_permission_for_user(doc_user, raise_exception=False)
