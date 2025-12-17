# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today
from uuid_utils import uuid7

from mail.jmap import get_jmap_client
from mail.utils import generate_uuid_style_hash, parse_filters
from mail.utils.dt import parse_iso_datetime
from mail.utils.validation import has_permission_for_user


class PushSubscription(Document):
	@property
	def _types(self) -> list[str]:
		"""Returns the types of push subscriptions as a list."""

		types = []
		if self.types:
			types = json.loads(self.types)

		return types

	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_push_subscription(
			self.user,
			self.device_client_id,
			self.url,
			self._types,
			ignore_permissions=bool(self.flags.ignore_permissions),
		)
		self.name = f"{self.user}|{self.id}"

	def load_from_db(self) -> "PushSubscription":
		user, id = self.name.split("|")
		subscription = get_push_subscription(user, id)
		return super(Document, self).__init__(subscription)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_push_subscription(user, id)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view push subscriptions."), alert=True)
			return []

		subscriptions = fetch_push_subscriptions(user, limit=page_length)

		if not subscriptions:
			frappe.msgprint(_("No push subscriptions found."), alert=True)

		return subscriptions

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
		self.validate_url()

	def validate_url(self) -> None:
		"""Validates the URL to ensure it starts with 'https://'."""

		if self.url and not self.url.startswith("https"):
			frappe.throw(_("The URL must start with 'https://'."))

	@frappe.whitelist()
	def renew(self) -> None:
		"""Renews the push subscription subscription."""

		renew_push_subscription(self.user, self.id)


def _get_total_cache_key(user: str) -> str:
	"""Returns a cache key for total push subscriptions count for the given user."""

	return f"{user}:push_subscriptions:total"


@frappe.whitelist()
def add_push_subscription(
	user: str,
	device_client_id: str | None = None,
	url: str | None = None,
	types: list[str] | None = None,
	ignore_permissions: bool = False,
) -> str:
	"""Adds a push subscription subscription for the given user and returns the subscription ID."""

	if not ignore_permissions:
		has_permission_for_user(user)

	device_client_id = device_client_id or generate_uuid_style_hash(
		f"frappe-{frappe.local.site.replace('.', '-')}-{user}"
	)
	url = url or f"{frappe.utils.get_url()}/api/method/mail.api.jmap.push_notification?user={user}"
	types = types or None

	creation_id = str(uuid7())
	client = get_jmap_client(user, ignore_permissions=ignore_permissions)
	response = client.push_subscription_create(creation_id, device_client_id, url, types)

	title = _("Push Subscription Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_push_subscription(user: str, id: str) -> dict:
	"""Returns push subscription details for the given name in the format 'user|id'."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	if subscriptions := client.push_subscription_get([id]):
		return format_push_subscription(user, subscriptions[0])


def verify_push_subscription(user: str, id: str, verification_code: str) -> None:
	"""Verifies a push subscription for the given user, subscription ID, and verification code."""

	if not frappe.db.exists("User", {"name": user, "enabled": 1}):
		frappe.throw(_("User does not exist or is disabled."))

	client = get_jmap_client(user, ignore_permissions=True)
	response = client.push_subscription_update(id, verification_code)

	if response[0][1].get("notUpdated"):
		frappe.throw(
			_(response[0][1]["notUpdated"][id]["description"]),
			title=_("Push Subscription Verification Error"),
		)


@frappe.whitelist()
def renew_push_subscription(user: str, id: str) -> None:
	"""Renews a push subscription subscription for the given user and subscription ID."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	response = client.push_subscription_update(id)

	if response[0][1].get("notUpdated"):
		frappe.throw(
			_(response[0][1]["notUpdated"][id]["description"]), title=_("Push Subscription Renewal Error")
		)


@frappe.whitelist()
def delete_push_subscription(user: str, id: str) -> None:
	"""Deletes a push subscription subscription for the given user and subscription ID."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	response = client.push_subscription_delete([id])

	if response.get("notDestroyed"):
		frappe.throw(
			_(response["notDestroyed"][id]["description"]), title=_("Push Subscription Deletion Error")
		)


@frappe.whitelist()
def fetch_push_subscriptions(user: str, page: int = 1, limit: int = 10) -> list:
	"""Fetches push subscriptions for the given user with pagination."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	subscriptions = client.push_subscription_get()
	formatted_subscriptions = [format_push_subscription(user, sub) for sub in subscriptions]
	frappe.cache.set_value(_get_total_cache_key(user), len(subscriptions), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_subscriptions[start:end]


def format_push_subscription(user: str, push_subscription: dict) -> dict:
	"""Formats push subscription data for display."""

	expires = parse_iso_datetime(push_subscription["expires"]) if push_subscription.get("expires") else None
	types = push_subscription.get("types") or []
	return {
		"user": user,
		"id": push_subscription["id"],
		"name": f"{user}|{push_subscription['id']}",
		"device_client_id": push_subscription["deviceClientId"],
		"expires": expires,
		"types": json.dumps(types, indent=4),
		"creation": today(),
		"modified": today(),
	}


def freeze_jmap_push_notifications(user: str) -> None:
	"""Freezes JMAP push notifications for the given user."""

	frappe.cache.hset("frozen_jmap_push_notifications", user, True)


def unfreeze_jmap_push_notifications(user: str) -> None:
	"""Unfreezes JMAP push notifications for the given user."""

	frappe.cache.hdel("frozen_jmap_push_notifications", user)


def is_jmap_push_notifications_frozen(user: str) -> bool:
	"""Returns True if JMAP push notifications are frozen for the given user."""

	return frappe.cache.hget("frozen_jmap_push_notifications", user) is True


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Push Subscription":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
