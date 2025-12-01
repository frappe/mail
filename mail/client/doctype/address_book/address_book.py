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
from mail.utils.validation import has_permission_for_user


class AddressBook(Document):
	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_address_book(
			self.user,
			self._name,
			self.description,
			self.sort_order,
			bool(self.default),
			bool(self.subscribed),
		)
		self.name = f"{self.user}|{self.id}"

	def load_from_db(self) -> "AddressBook":
		user, id = self.name.split("|")
		address_book = get_address_book(user, id)
		return super(Document, self).__init__(address_book)

	def db_update(self) -> None:
		update_address_book(
			self.user,
			self.id,
			self._name,
			self.description,
			self.sort_order,
			bool(self.default),
			bool(self.subscribed),
		)
		self.reload()

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_address_book(user, id)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view address books."), alert=True)
			return []

		address_books = fetch_address_books(user, limit=page_length)

		if not address_books:
			frappe.msgprint(_("No address book found."), alert=True)

		return address_books

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


def validate_address_book_name_format(name: str) -> None:
	"""Validates that the address book name is in the format 'user|id'."""

	parts = name.split("|")
	if len(parts) != 2:
		frappe.throw(_("Address Book name must be in the format 'user|id'."))


def _get_total_cache_key(user: str) -> str:
	"""Returns a cache key for total address books count for the given user."""

	return f"{user}:address_books:total"


@frappe.whitelist()
def add_address_book(
	user: str,
	name: str,
	description: str | None = None,
	sort_order: int = 0,
	default: bool = False,
	subscribed: bool = True,
) -> str:
	"""Adds a address book for the given user with the specified parameters."""

	has_permission_for_user(user)

	creation_id = str(uuid7())
	client = get_jmap_client(user)
	response = client.address_book_create(creation_id, name, description, sort_order, default, subscribed)

	title = _("Address Book Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_address_book(user: str, id: str) -> dict:
	"""Returns address book details for the given name in the format 'user|id'."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	if address_books := client.address_book_get([id]):
		return format_address_book(user, address_books[0])

	frappe.throw(
		_("Address Book with ID {0} not found in user {1}.").format(frappe.bold(id), frappe.bold(user)),
		title=_("Address Book Not Found"),
	)


@frappe.whitelist()
def update_address_book(
	user: str,
	id: str,
	name: str,
	description: str | None = None,
	sort_order: int = 0,
	default: bool = False,
	subscribed: bool = True,
) -> None:
	"""Updates an existing address book with the given parameters."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	response = client.address_book_update(id, name, description, sort_order, default, subscribed)

	title = _("Address Book Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_address_book(user: str, id: str) -> None:
	"""Deletes a address book for the given user by its ID."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	response = client.address_book_delete([id], remove_contents=True)

	if response.get("notDestroyed"):
		frappe.throw(_(response["notDestroyed"][id]["description"]), title=_("Address Book Deletion Error"))


@frappe.whitelist()
def fetch_address_books(user: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of address books for the given user."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	address_books = client.address_book_get()
	formatted_address_books = [format_address_book(user, book) for book in address_books]
	sorted_address_books = sorted(formatted_address_books, key=lambda x: x["sort_order"])
	frappe.cache.set_value(_get_total_cache_key(user), len(address_books), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return sorted_address_books[start:end]


def format_address_book(user: str, address_book: dict) -> dict:
	"""Formats address book data for display."""

	sort_order = cint(address_book["sortOrder"])
	if rights := address_book.get("myRights"):
		rights = json.dumps(rights, indent=4, sort_keys=True)

	return {
		"name": f"{user}|{address_book['id']}",
		"user": user,
		"id": address_book["id"],
		"_name": address_book["name"],
		"sort_order": sort_order,
		"description": address_book["description"],
		"default": bool(address_book["isDefault"]),
		"subscribed": bool(address_book["isSubscribed"]),
		"rights": rights,
		"creation": today(),
		"modified": today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Address Book":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
