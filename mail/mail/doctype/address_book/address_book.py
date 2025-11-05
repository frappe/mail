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


class AddressBook(Document):
	def db_insert(self, *args, **kwargs) -> None:
		has_permission_for_account(self.account)
		self.id = add_address_book(
			self.account,
			self._name,
			self.description,
			self.sort_order,
			bool(self.default),
			bool(self.subscribed),
		)
		self.name = f"{self.account}|{self.id}"

	def load_from_db(self) -> "AddressBook":
		account, id = self.name.split("|")
		has_permission_for_account(account)
		address_book = get_address_book(account, id)
		return super(Document, self).__init__(address_book)

	def db_update(self) -> None:
		has_permission_for_account(self.account)
		update_address_book(
			self.account,
			self.id,
			self._name,
			self.description,
			self.sort_order,
			bool(self.default),
			bool(self.subscribed),
		)
		self.reload()

	def delete(self) -> None:
		account, id = self.name.split("|")
		has_permission_for_account(account)
		delete_address_book(account, id)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		account = filters.get("account") or get_account_for_user(frappe.session.user)

		if not account:
			frappe.msgprint(_("Please select a account to view address books."), alert=True)
			return []

		has_permission_for_account(account)
		address_books = fetch_address_books(account, limit=page_length)

		if not address_books:
			frappe.msgprint(_("No address book found."), alert=True)

		return address_books

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		account = filters.get("account") or get_account_for_user(frappe.session.user)
		return frappe.cache.get_value(get_total_cache_key(account)) if account else 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}


def get_total_cache_key(account: str) -> str:
	"""Returns a cache key for total address books count for the given account."""

	return f"{account}:address_books:total"


def add_address_book(
	account: str,
	name: str,
	description: str | None = None,
	sort_order: int = 0,
	default: bool = False,
	subscribed: bool = True,
) -> str:
	"""Adds a address book for the given account with the specified parameters."""

	unique_id = str(uuid7())
	client = get_jmap_client(account)
	response = client.address_book_create(unique_id, name, description, sort_order, default, subscribed)

	title = _("Address Book Creation Error")
	if response.get("created"):
		return response["created"][unique_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][unique_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


def get_address_book(account: str, id: str) -> dict:
	"""Returns address book details for the given name in the format 'account|id'."""

	client = get_jmap_client(account)
	if address_books := client.address_book_get([id]):
		return format_address_book(account, address_books[0])

	frappe.throw(
		_("Address Book with ID {0} not found in account {1}.").format(frappe.bold(id), frappe.bold(account)),
		title=_("Address Book Not Found"),
	)


def update_address_book(
	account: str,
	id: str,
	name: str,
	description: str | None = None,
	sort_order: int = 0,
	default: bool = False,
	subscribed: bool = True,
) -> None:
	"""Updates an existing address book with the given parameters."""

	client = get_jmap_client(account)
	response = client.address_book_update(id, name, description, sort_order, default, subscribed)

	title = _("Address Book Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


def delete_address_book(account: str, id: str) -> None:
	"""Deletes a address book for the given account by its ID."""

	client = get_jmap_client(account)
	response = client.address_book_delete([id], remove_contents=True)

	if response.get("notDestroyed"):
		frappe.throw(_(response["notDestroyed"][id]["description"]), title=_("Address Book Deletion Error"))


def fetch_address_books(account: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of address books for the given account."""

	client = get_jmap_client(account)
	address_books = client.address_book_get()
	formatted_address_books = [format_address_book(account, book) for book in address_books]
	sorted_address_books = sorted(formatted_address_books, key=lambda x: x["sort_order"])
	frappe.cache.set_value(get_total_cache_key(account), len(address_books), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return sorted_address_books[start:end]


def format_address_book(account: str, address_book: dict) -> dict:
	"""Formats address book data for display."""

	sort_order = cint(address_book["sortOrder"])
	if rights := address_book.get("myRights"):
		rights = json.dumps(rights, indent=4, sort_keys=True)

	return {
		"name": f"{account}|{address_book['id']}",
		"account": account,
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

	user = user or frappe.session.user

	if is_administrator(user):
		return True

	if has_role(user, "Mail User"):
		return doc.account == get_account_for_user(user)

	return False
