# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today
from uuid_utils import uuid7

from mail.jmap import get_jmap_client
from mail.utils import parse_filters
from mail.utils.cache import get_account_for_user
from mail.utils.dt import parse_iso_datetime
from mail.utils.user import has_role, is_administrator
from mail.utils.validation import has_permission_for_account


class ContactCard(Document):
	@property
	def address_book_ids(self) -> list[str]:
		"""Returns a list of address book IDs associated with this contact card."""

		address_book_ids = []
		for address_book in self.address_books:
			address_book_id = address_book.get("address_book_id")
			if not address_book_id:
				frappe.throw(_("Row #{0}: Address Book ID is required.").format(address_book.idx))
			address_book_ids.append(address_book_id)

		return address_book_ids

	@property
	def formatted_emails(self) -> dict[str, list[str]] | None:
		"""Returns emails in the format required by JMAP API."""

		if self.emails:
			emails = {}
			for email in self.emails:
				emails.setdefault(email.type, set()).add(email.address)

			return {k: list(v) for k, v in emails.items()}

	@property
	def formatted_phones(self) -> dict[str, list[str]] | None:
		"""Returns phones in the format required by JMAP API."""

		if self.phones:
			phones = {}
			for phone in self.phones:
				phones.setdefault(phone.type, set()).add(phone.number)

			return {k: list(v) for k, v in phones.items()}

	def db_insert(self, *args, **kwargs) -> None:
		has_permission_for_account(self.account)
		self.id = add_contact_card(
			self.account,
			self.address_book_ids,
			self.full_name,
			self.formatted_emails,
			self.formatted_phones,
			self.kind,
		)
		self.name = f"{self.account}|{self.id}"

	def load_from_db(self) -> "ContactCard":
		account, id = self.name.split("|")
		has_permission_for_account(account)
		contact_card = get_contact_card(account, id)
		return super(Document, self).__init__(contact_card)

	def db_update(self) -> None:
		has_permission_for_account(self.account)
		update_contact_card(
			self.account,
			self.id,
			self.address_book_ids,
			self.full_name,
			self.formatted_emails,
			self.formatted_phones,
			self.kind,
		)
		self.reload()

	def delete(self) -> None:
		account, id = self.name.split("|")
		has_permission_for_account(account)
		delete_contact_card(account, id)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		account = filters.get("account") or get_account_for_user(frappe.session.user)

		if not account:
			frappe.msgprint(_("Please select a account to view contact cards."), alert=True)
			return []

		has_permission_for_account(account)
		contact_cards = fetch_contact_cards(account, limit=page_length)

		if not contact_cards:
			frappe.msgprint(_("No contact card found."), alert=True)

		return contact_cards

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		account = filters.get("account") or get_account_for_user(frappe.session.user)
		return frappe.cache.get_value(get_total_cache_key(account)) if account else 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	def validate(self) -> None:
		self.validate_address_books()

	def validate_address_books(self) -> None:
		"""Validates that at least one address book is associated with the contact card."""

		if not self.address_books:
			frappe.throw(_("A contact card must belong to at least one address book."))

		for ab in self.address_books:
			address_book = frappe.get_doc("Address Book", ab.address_book)
			ab.address_book_id = address_book.id
			ab.address_book_name = address_book._name


def get_total_cache_key(account: str) -> str:
	"""Returns a cache key for total contact cards count for the given account."""

	return f"{account}:contact_cards:total"


def add_contact_card(
	account: str,
	address_book_ids: list[str],
	full_name: str | None = None,
	emails: dict[str, list[str]] | None = None,
	phones: dict[str, list[str]] | None = None,
	kind: str = "individual",
) -> str:
	"""Adds a contact card for the given account with the specified parameters."""

	creation_id = str(uuid7())
	client = get_jmap_client(account)
	response = client.contact_card_create(creation_id, address_book_ids, full_name, emails, phones, kind)

	title = _("Contact Card Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


def get_contact_card(account: str, id: str) -> dict:
	"""Returns contact card details for the given name in the format 'account|id'."""

	client = get_jmap_client(account)
	if contact_cards := client.contact_card_get([id]):
		return format_contact_card(account, contact_cards[0])

	frappe.throw(
		_("Contact Card with ID {0} not found in account {1}.").format(frappe.bold(id), frappe.bold(account)),
		title=_("Contact Card Not Found"),
	)


def update_contact_card(
	account: str,
	id: str,
	address_book_ids: list[str],
	full_name: str | None = None,
	emails: dict[str, list[str]] | None = None,
	phones: dict[str, list[str]] | None = None,
	kind: str = "individual",
) -> None:
	"""Updates an existing contact card with the given parameters."""

	client = get_jmap_client(account)
	response = client.contact_card_update(id, address_book_ids, full_name, emails, phones, kind)

	title = _("Contact Card Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


def delete_contact_card(account: str, id: str) -> None:
	"""Deletes a contact card for the given account by its ID."""

	client = get_jmap_client(account)
	response = client.contact_card_delete([id])

	if response.get("notDestroyed"):
		frappe.throw(_(response["notDestroyed"][id]["description"]), title=_("Contact Card Deletion Error"))


def fetch_contact_cards(account: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of contact cards for the given account."""

	client = get_jmap_client(account)
	contact_cards = client.contact_card_get()
	formatted_contact_cards = [format_contact_card(account, card) for card in contact_cards]
	frappe.cache.set_value(get_total_cache_key(account), len(contact_cards), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_contact_cards[start:end]


def format_contact_card(account: str, contact_card: dict) -> dict:
	"""Formats contact card data for display."""

	full_name = None
	if contact_card.get("name"):
		if components := contact_card["name"].get("components"):
			if contact_card["name"].get("isOrdered", False):
				full_name = " ".join([component["value"] for component in components])
			else:
				given = next(
					(component["value"] for component in components if component["kind"] == "given"), ""
				)
				surname = next(
					(component["value"] for component in components if component["kind"] == "surname"), ""
				)
				full_name = f"{given} {surname}".strip()

	address_books = []
	for address_book_id in contact_card["addressBookIds"].keys():
		address_book = f"{account}|{address_book_id}"
		address_book_doc = frappe.get_doc("Address Book", address_book)
		address_books.append(
			{
				"address_book": address_book,
				"address_book_id": address_book_id,
				"address_book_name": address_book_doc._name,
			}
		)

	emails = []
	for email in contact_card.get("emails", {}).values():
		address = email.get("address")
		contexts = email.get("contexts", {})
		type = next(context for context in contexts.keys()) if contexts else None
		emails.append(
			{
				"type": type,
				"address": address,
				"contexts": json.dumps(contexts, indent=4),
			}
		)

	phones = []
	for phone in contact_card.get("phones", {}).values():
		number = phone.get("number")
		contexts = phone.get("contexts", {})
		type = next(context for context in contexts.keys()) if contexts else None
		phones.append(
			{
				"type": type,
				"number": number,
				"contexts": json.dumps(contexts, indent=4),
			}
		)

	creation = modified = None
	if contact_card.get("created"):
		creation = parse_iso_datetime(contact_card["created"], as_str=True)
	if contact_card.get("updated"):
		modified = parse_iso_datetime(contact_card["updated"], as_str=True)

	return {
		"name": f"{account}|{contact_card['id']}",
		"account": account,
		"id": contact_card["id"],
		"kind": contact_card.get("kind"),
		"name_breakup": json.dumps(contact_card.get("name", {}), indent=4),
		"full_name": full_name,
		"address_books": address_books,
		"emails": emails,
		"phones": phones,
		"created_at": contact_card.get("created"),
		"updated_at": contact_card.get("updated"),
		"creation": creation or modified or today(),
		"modified": modified or creation or today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Contact Card":
		return False

	user = user or frappe.session.user

	if is_administrator(user):
		return True

	if has_role(user, "Mail User"):
		return doc.account == get_account_for_user(user)

	return False
