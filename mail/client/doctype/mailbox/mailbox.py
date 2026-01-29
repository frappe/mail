# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from mail.jmap import get_jmap_client
from mail.utils import batch_dict, parse_filters
from mail.utils.validation import has_permission_for_user

DEFAULT_MAILBOX_GAP = 1000
MINIMUM_MAILBOX_GAP = 1
REBALANCE_MAILBOX_WINDOW = 10


class Mailbox(Document):
	def db_insert(self, *args, **kwargs) -> None:
		parent = self._parent.replace(f"{self.user}|", "") if self._parent else None
		self.id = add_mailbox(
			self.user, self._name, self.role, parent, self.sort_order, bool(self.subscribed)
		)
		self.name = f"{self.user}|{self.id}"

	def load_from_db(self) -> "Mailbox":
		user, id = self.name.split("|")
		mailbox = get_mailbox(user, id)
		return super(Document, self).__init__(mailbox)

	def db_update(self) -> None:
		parent = self._parent.replace(f"{self.user}|", "") if self._parent else None
		update_mailbox(
			self.user, self.id, self._name, self.role, parent, self.sort_order, bool(self.subscribed)
		)
		self.reload()

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_mailboxes(user, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view mailboxes."), alert=True)
			return []

		mailboxes = fetch_mailboxes(user, limit=page_length)

		if not mailboxes:
			frappe.msgprint(_("No mailboxes found."), alert=True)

		return mailboxes

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
	"""Returns a cache key for total mailbox count for the given user."""

	return f"{user}:mailboxes:total"


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes multiple mailboxes given their names."""

	if isinstance(names, str):
		names = json.loads(names)

	user_ids_map = {}
	for name in names:
		user, id = name.split("|")
		user_ids_map.setdefault(user, []).append(id)

	for user, ids in user_ids_map.items():
		delete_mailboxes(user, ids)

	frappe.msgprint(_("Mailboxes deleted successfully."), alert=True)


@frappe.whitelist()
def add_mailbox(
	user: str,
	name: str,
	role: str | None = None,
	parent: str | None = None,
	sort_order: int = 0,
	subscribed: bool = True,
) -> str:
	"""Adds a mailbox for the given user with the specified parameters."""

	has_permission_for_user(user)

	creation_id = str(uuid7())
	client = get_jmap_client(user)
	response = client.mailbox_create(creation_id, name, role, parent, sort_order, subscribed)

	title = _("Mailbox Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_mailbox(user: str, id: str) -> dict:
	"""Returns mailbox details for the given name in the format 'user|id'."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	if mailboxes := client.mailbox_get([id]):
		return format_mailbox(user, mailboxes[0])

	frappe.throw(
		_("Mailbox with ID {0} not found in user {1}.").format(frappe.bold(id), frappe.bold(user)),
		title=_("Mailbox Not Found"),
	)


@frappe.whitelist()
def update_mailbox(
	user: str,
	id: str,
	name: str,
	role: str | None = None,
	parent: str | None = None,
	sort_order: int = 0,
	subscribed: bool = True,
) -> None:
	"""Updates an existing mailbox with the given parameters."""

	has_permission_for_user(user)

	title = _("Mailbox Update Error")
	if parent and id == parent:
		frappe.throw(_("Mailbox cannot be a parent of itself."), title=title)

	client = get_jmap_client(user)
	response = client.mailbox_update(id, name, role, parent, sort_order, subscribed)

	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_mailboxes(user: str, ids: list[str], remove_emails: bool = True) -> None:
	"""Deletes a mailbox for the given user by its ID."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	response = client.mailbox_delete(ids, remove_emails=remove_emails)

	if response.get("notDestroyed"):
		error_messages = []
		for id, error in response["notDestroyed"].items():
			error_messages.append(f"{id}: {error['description']}")
		frappe.throw(
			_("Mailbox Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
			title=_("Mailbox Deletion Error"),
		)


@frappe.whitelist()
def fetch_mailboxes(user: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of mailboxes for the given user."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	mailboxes = client.mailbox_get()
	formatted_mailboxes = [format_mailbox(user, mailbox) for mailbox in mailboxes]
	sorted_mailboxes = sorted(
		formatted_mailboxes, key=lambda m: (m["sort_order"], get_sort_order(m["role"]), m["_name"], m["id"])
	)
	frappe.cache.set_value(_get_total_cache_key(user), len(mailboxes), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return sorted_mailboxes[start:end]


@frappe.whitelist()
def update_mailbox_position(user: str, target_mailbox_id: str, prior_mailbox_id: str | None = None) -> None:
	"""Updates the position of the target mailbox to be after the prior mailbox."""

	def get_updates(
		mailboxes: list[dict], target_mailbox_id: str, prior_mailbox_id: str | None
	) -> dict[str, int]:
		"""Returns the sort order updates required to move the target mailbox after the prior mailbox."""

		index = {m["id"]: i for i, m in enumerate(mailboxes)}

		if target_mailbox_id not in index:
			frappe.throw(_("Target mailbox ID {0} not found.").format(frappe.bold(target_mailbox_id)))

		mailboxes.pop(index[target_mailbox_id])
		index = {m["id"]: i for i, m in enumerate(mailboxes)}

		# Prior mailbox is None, place at start
		if prior_mailbox_id is None:
			lower = None
			upper = mailboxes[0]["sortOrder"] if mailboxes else None
			insert_index = 0

		# Prior mailbox is specified, place after it
		else:
			if prior_mailbox_id not in index:
				frappe.throw(_("Prior mailbox ID {0} not found.").format(frappe.bold(prior_mailbox_id)))

			prior_index = index[prior_mailbox_id]
			lower = mailboxes[prior_index]["sortOrder"]
			insert_index = prior_index + 1
			upper = mailboxes[insert_index]["sortOrder"] if insert_index < len(mailboxes) else None

		# Case - 1: Both lower and upper bounds exist and have enough gap, create in between
		if lower is not None and upper is not None and upper - lower > MINIMUM_MAILBOX_GAP:
			new_sort = (lower + upper) // 2
			return {target_mailbox_id: new_sort}

		# Case - 2: Only lower bound exists, place after it
		if lower is not None and upper is None:
			return {target_mailbox_id: lower + DEFAULT_MAILBOX_GAP}

		# Case - 3: Only upper bound exists, place before it
		if lower is None and upper is not None:
			return {target_mailbox_id: upper - DEFAULT_MAILBOX_GAP}

		# Case - 4: Neither bound exists, place at start
		if lower is None and upper is None:
			return {target_mailbox_id: 0}

		# If there is no gap, rebalance
		start = max(0, insert_index - REBALANCE_MAILBOX_WINDOW)
		end = min(len(mailboxes), insert_index + REBALANCE_MAILBOX_WINDOW)

		window = mailboxes[start:end]

		base = window[0]["sortOrder"]
		base = (base // DEFAULT_MAILBOX_GAP) * DEFAULT_MAILBOX_GAP

		updates: dict[str, int] = {}
		current = base

		target_slot = insert_index - start

		for i, m in enumerate(window):
			if i == target_slot:
				current += DEFAULT_MAILBOX_GAP

			current += DEFAULT_MAILBOX_GAP
			if m["sortOrder"] != current:
				updates[m["id"]] = current

		target_sort_order = base + DEFAULT_MAILBOX_GAP * (target_slot + 1)
		updates[target_mailbox_id] = target_sort_order

		return updates

	has_permission_for_user(user)

	client = get_jmap_client(user)
	mailboxes = sorted(
		client.mailbox_get(), key=lambda m: (m["sortOrder"], get_sort_order(m["role"]), m["name"], m["id"])
	)
	updates = get_updates(mailboxes, target_mailbox_id, prior_mailbox_id)

	result = {"updated": {}, "notUpdated": {}}
	for updates_batch in batch_dict(updates, client.max_objects_in_set):
		response = client._make_request(
			using=["urn:ietf:params:jmap:mail"],
			method_calls=[
				[
					"Mailbox/set",
					{
						"accountId": client.primary_account_id,
						"update": {k: {"sortOrder": v} for k, v in updates_batch.items()},
					},
					"0",
				]
			],
		)

		result["updated"].update(response["methodResponses"][0][1].get("updated", {}))
		if not_updated := response["methodResponses"][0][1].get("notUpdated", {}):
			result["notUpdated"].update(not_updated)

	title = _("Mailbox Position Update Error")
	if not result.get("updated"):
		frappe.throw(_(result["description"]), title=title)


def format_mailbox(user: str, mailbox: dict) -> dict:
	"""Formats mailbox data for display."""

	sort_order = cint(mailbox["sortOrder"])
	if _parent := mailbox["parentId"]:
		_parent = f"{user}|{_parent}"
	rights = mailbox.get("myRights") or {}

	return {
		"name": f"{user}|{mailbox['id']}",
		"user": user,
		"id": mailbox["id"],
		"_name": mailbox["name"],
		"_parent": _parent,
		"parent_id": mailbox["parentId"],
		"role": mailbox["role"],
		"sort_order": sort_order,
		"subscribed": bool(mailbox["isSubscribed"]),
		"total_emails": cint(mailbox["totalEmails"]),
		"unread_emails": cint(mailbox["unreadEmails"]),
		"total_threads": cint(mailbox["totalThreads"]),
		"unread_threads": cint(mailbox["unreadThreads"]),
		"may_read_items": cint(rights.get("mayReadItems", False)),
		"may_add_items": cint(rights.get("mayAddItems", False)),
		"may_remove_items": cint(rights.get("mayRemoveItems", False)),
		"may_set_seen": cint(rights.get("maySetSeen", False)),
		"may_set_keywords": cint(rights.get("maySetKeywords", False)),
		"may_create_child": cint(rights.get("mayCreateChild", False)),
		"may_rename": cint(rights.get("mayRename", False)),
		"may_delete": cint(rights.get("mayDelete", False)),
		"may_submit": cint(rights.get("maySubmit", False)),
		"creation": today(),
		"modified": today(),
	}


def get_sort_order(role: str | None = None) -> int:
	"""Returns the sort order for the mailbox based on its role."""

	role_order = ["inbox", "important", "sent", "drafts", "junk", "archive", "trash"]

	if not role or role not in role_order:
		return len(role_order) + 1

	return role_order.index(role)


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mailbox":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
