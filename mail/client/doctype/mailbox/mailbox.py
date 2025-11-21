# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today
from uuid_utils import uuid7

from mail.jmap import get_jmap_client
from mail.utils import parse_filters
from mail.utils.cache import get_account_for_user
from mail.utils.user import has_role, is_administrator
from mail.utils.validation import has_permission_for_account


class Mailbox(Document):
	def db_insert(self, *args, **kwargs) -> None:
		parent = self._parent.replace(f"{self.account}|", "") if self._parent else None
		self.id = add_mailbox(
			self.account, self._name, self.role, parent, self.sort_order, bool(self.subscribed)
		)
		self.name = f"{self.account}|{self.id}"

	def load_from_db(self) -> "Mailbox":
		account, id = self.name.split("|")
		mailbox = get_mailbox(account, id)
		return super(Document, self).__init__(mailbox)

	def db_update(self) -> None:
		parent = self._parent.replace(f"{self.account}|", "") if self._parent else None
		update_mailbox(
			self.account, self.id, self._name, self.role, parent, self.sort_order, bool(self.subscribed)
		)
		self.reload()

	def delete(self) -> None:
		account, id = self.name.split("|")
		delete_mailbox(account, id)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		account = filters.get("account") or get_account_for_user(frappe.session.user)

		if not account:
			frappe.msgprint(_("Please select a account to view mailboxes."), alert=True)
			return []

		mailboxes = fetch_mailboxes(account, limit=page_length)

		if not mailboxes:
			frappe.msgprint(_("No mailboxes found."), alert=True)

		return mailboxes

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		account = filters.get("account") or get_account_for_user(frappe.session.user)
		return frappe.cache.get_value(get_total_cache_key(account)) if account else 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}


def get_total_cache_key(account: str) -> str:
	"""Returns a cache key for total mailbox count for the given account."""

	return f"{account}:mailboxes:total"


@frappe.whitelist()
def add_mailbox(
	account: str,
	name: str,
	role: str | None = None,
	parent: str | None = None,
	sort_order: int = 0,
	subscribed: bool = True,
) -> str:
	"""Adds a mailbox for the given account with the specified parameters."""

	has_permission_for_account(account)

	creation_id = str(uuid7())
	client = get_jmap_client(account)
	response = client.mailbox_create(creation_id, name, role, parent, sort_order, subscribed)

	title = _("Mailbox Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_mailbox(account: str, id: str) -> dict:
	"""Returns mailbox details for the given name in the format 'account|id'."""

	has_permission_for_account(account)

	client = get_jmap_client(account)
	if mailboxes := client.mailbox_get([id]):
		return format_mailbox(account, mailboxes[0])

	frappe.throw(
		_("Mailbox with ID {0} not found in account {1}.").format(frappe.bold(id), frappe.bold(account)),
		title=_("Mailbox Not Found"),
	)


@frappe.whitelist()
def update_mailbox(
	account: str,
	id: str,
	name: str,
	role: str | None = None,
	parent: str | None = None,
	sort_order: int = 0,
	subscribed: bool = True,
) -> None:
	"""Updates an existing mailbox with the given parameters."""

	has_permission_for_account(account)

	title = _("Mailbox Update Error")
	if parent and id == parent:
		frappe.throw(_("Mailbox cannot be a parent of itself."), title=title)

	client = get_jmap_client(account)
	response = client.mailbox_update(id, name, role, parent, sort_order, subscribed)

	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_mailbox(account: str, id: str, remove_emails: bool = True) -> None:
	"""Deletes a mailbox for the given account by its ID."""

	has_permission_for_account(account)

	client = get_jmap_client(account)
	response = client.mailbox_delete([id], remove_emails=remove_emails)

	if response.get("notDestroyed"):
		frappe.throw(_(response["notDestroyed"][id]["description"]), title=_("Mailbox Deletion Error"))


@frappe.whitelist()
def fetch_mailboxes(account: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of mailboxes for the given account."""

	has_permission_for_account(account)

	client = get_jmap_client(account)
	mailboxes = client.mailbox_get()
	formatted_mailboxes = [format_mailbox(account, mailbox) for mailbox in mailboxes]
	sorted_mailboxes = sorted(
		formatted_mailboxes,
		key=lambda m: (m.get("_sort_order") == 0, m.get("_sort_order", float("inf")), m.get("_name")),
	)
	frappe.cache.set_value(get_total_cache_key(account), len(mailboxes), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return sorted_mailboxes[start:end]


def format_mailbox(account: str, mailbox: dict) -> dict:
	"""Formats mailbox data for display."""

	sort_order = cint(mailbox["sortOrder"])
	if _parent := mailbox["parentId"]:
		_parent = f"{account}|{_parent}"
	if rights := mailbox.get("myRights"):
		rights = json.dumps(rights, indent=4, sort_keys=True)

	return {
		"name": f"{account}|{mailbox['id']}",
		"account": account,
		"id": mailbox["id"],
		"_name": mailbox["name"],
		"_parent": _parent,
		"parent_id": mailbox["parentId"],
		"role": mailbox["role"],
		"sort_order": sort_order,
		"_sort_order": sort_order or get_sort_order(mailbox["role"]),
		"subscribed": bool(mailbox["isSubscribed"]),
		"total_emails": cint(mailbox["totalEmails"]),
		"unread_emails": cint(mailbox["unreadEmails"]),
		"total_threads": cint(mailbox["totalThreads"]),
		"unread_threads": cint(mailbox["unreadThreads"]),
		"rights": rights,
		"creation": today(),
		"modified": today(),
	}


def get_sort_order(role: str | None = None) -> int:
	"""Returns the sort order for the mailbox based on its role."""

	role_order = ["inbox", "important", "sent", "drafts", "junk", "archive", "trash"]

	if not role or role not in role_order:
		return 0

	return role_order.index(role) + 1


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mailbox":
		return False

	user = user or frappe.session.user

	if is_administrator(user):
		return True

	if has_role(user, "Mail User"):
		return doc.account == get_account_for_user(user)

	return False
