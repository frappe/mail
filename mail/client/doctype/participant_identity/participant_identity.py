# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today
from uuid_utils import uuid7

from mail.jmap import get_jmap_client
from mail.utils import parse_filters
from mail.utils.validation import has_permission_for_user


class ParticipantIdentity(Document):
	@property
	def calendar_address(self) -> str:
		"""Returns the calendar address in mailto format."""

		return f"mailto:{self.email.lower()}"

	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_participant_identity(
			self.user,
			self._name,
			self.email,
			bool(self.default),
		)
		self.name = f"{self.user}|{self.id}"

	def load_from_db(self) -> "ParticipantIdentity":
		user, id = self.name.split("|")
		identity = get_participant_identity(user, id)
		return super(Document, self).__init__(identity)

	def db_update(self) -> None:
		update_participant_identity(
			self.user,
			self.id,
			self._name,
			self.email,
			bool(self.default),
		)
		self.reload()

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_participant_identities(user, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view participant identities."), alert=True)
			return []

		identities = fetch_participant_identities(user, limit=page_length)

		if not identities:
			frappe.msgprint(_("No participant identities found."), alert=True)

		return identities

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
	"""Returns a cache key for total participant identities count for the given user."""

	return f"{user}:participant_identities:total"


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes participant identities for the given list of names."""

	if isinstance(names, str):
		names = json.loads(names)

	user_ids_map = {}
	for name in names:
		user, id = name.split("|")
		user_ids_map.setdefault(user, []).append(id)

	for user, ids in user_ids_map.items():
		delete_participant_identities(user, ids)

	frappe.msgprint(_("Participant Identities deleted successfully."), alert=True)


@frappe.whitelist()
def add_participant_identity(user: str, name: str, email: str, default: bool = False) -> str:
	"""Adds a participant identity for the given user and returns the identity ID."""

	has_permission_for_user(user)

	creation_id = str(uuid7())
	client = get_jmap_client(user)
	response = client.participant_identity_create(creation_id, name, email, default)

	title = _("Participant Identity Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_participant_identity(user: str, id: str) -> dict:
	"""Returns participant identity details for the given user and identity ID."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	if identities := client.participant_identity_get([id]):
		return format_participant_identity(user, identities[0])

	frappe.throw(
		_("Participant Identity with ID {0} not found in user {1}.").format(
			frappe.bold(id), frappe.bold(user)
		),
		title=_("Participant Identity Not Found"),
	)


@frappe.whitelist()
def update_participant_identity(user: str, id: str, name: str, email: str, default: bool = False) -> None:
	"""Updates an existing participant identity with the given parameters."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	response = client.participant_identity_update(id, name, email, default)

	if not response.get("updated"):
		title = _("Participant Identity Update Error")
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_participant_identities(user: str, ids: list[str]) -> None:
	"""Deletes participant identities for the specified user and ID(s)."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	response = client.participant_identity_delete(ids)

	if response.get("notDestroyed"):
		error_messages = []
		for id, error in response["notDestroyed"].items():
			error_messages.append(f"{id}: {error['description']}")
		frappe.throw(
			_("Participant Identity Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
			title=_("Participant Identity Deletion Error"),
		)


@frappe.whitelist()
def fetch_participant_identities(user: str, page: int = 1, limit: int = 10) -> list:
	"""Fetches and returns all participant identities for the given user."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	identities = client.participant_identity_get()
	formatted_identities = [format_participant_identity(user, identity) for identity in identities]
	frappe.cache.set_value(_get_total_cache_key(user), len(identities), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_identities[start:end]


def format_participant_identity(user: str, identity: dict) -> dict:
	"""Formats participant identity data for display."""

	return {
		"name": f"{user}|{identity['id']}",
		"user": user,
		"id": identity["id"],
		"default": cint(bool(identity["isDefault"])),
		"_name": identity["name"],
		"email": identity["calendarAddress"].split("mailto:")[-1].lower(),
		"creation": today(),
		"modified": today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Participant Identity":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
