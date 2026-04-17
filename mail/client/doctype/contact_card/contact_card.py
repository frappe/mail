# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from mail.client.doctype.address_book.address_book import validate_address_book_name_format
from mail.jmap import get_contact_card_service, parse_account
from mail.utils import get_mail_config, parse_filters
from mail.utils.dt import parse_iso_datetime
from mail.utils.validation import has_permission_for_user


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
	def formatted_emails(self) -> list[dict] | None:
		"""Returns emails in the format required by JMAP API."""

		if self.emails:
			emails = []
			for email in self.emails:
				emails.append(
					{
						"type": email.type,
						"label": email.label,
						"address": email.address,
					}
				)

			return emails

	@property
	def formatted_phones(self) -> list[dict] | None:
		"""Returns phones in the format required by JMAP API."""

		if self.phones:
			phones = []
			for phone in self.phones:
				phones.append(
					{
						"type": phone.type,
						"label": phone.label,
						"number": phone.number,
					}
				)

			return phones

	@property
	def formatted_addresses(self) -> list[dict] | None:
		"""Returns addresses in the format required by JMAP API."""

		if self.addresses:
			addresses = []
			for address in self.addresses:
				addresses.append(
					{
						"type": address.type,
						"street": address.street,
						"locality": address.locality,
						"region": address.region,
						"country": address.country,
						"postcode": address.postcode,
						"time_zone": address.time_zone,
					}
				)

			return addresses

	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_contact_card(
			self.account,
			self.address_book_ids,
			self.full_name,
			self.formatted_emails,
			self.formatted_phones,
			self.formatted_addresses,
			self.kind,
		)
		self.name = f"{self.account}|{self.id}"

	def load_from_db(self) -> "ContactCard":
		account, id = self.name.split("|")
		if contact_cards := get_contact_cards(account, [id]):
			return super(Document, self).__init__(contact_cards[0])

		frappe.throw(
			_("Contact Card with ID {0} not found in account {1}.").format(
				frappe.bold(id), frappe.bold(account)
			),
			title=_("Contact Card Not Found"),
		)

	def db_update(self) -> None:
		update_contact_card(
			self.account,
			self.id,
			self.address_book_ids,
			self.full_name,
			self.formatted_emails,
			self.formatted_phones,
			self.formatted_addresses,
			self.kind,
		)
		self.reload()

	def delete(self) -> None:
		account, id = self.name.split("|")
		delete_contact_cards(account, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)

		id = filters.get("id")
		account = filters.get("account")

		if not account:
			frappe.msgprint(_("Please select an account to view contact cards."), alert=True)
			return []

		if id:
			contact_cards = get_contact_cards(account, [id])
			total = len(contact_cards)
		else:
			if address_book := filters.get("address_book"):
				validate_address_book_name_format(address_book)
				filters["address_book"] = address_book.split("|")[1]

			filter = {
				prop: value
				for field, prop in {
					"address_book": "inAddressBook",
					"full_name": "name",
					"email": "email",
					"phone": "phone",
				}.items()
				if (value := filters.get(field))
			}
			limit = cint(kwargs.get("start")) + page_length
			contact_cards, total = fetch_contact_cards(account, filter, limit=limit)

		frappe.cache.set_value(_get_total_cache_key(account), total, expires_in_sec=600)

		if not contact_cards:
			frappe.msgprint(_("No contact card found."), alert=True)

		return contact_cards

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		account = filters.get("account")

		if account:
			if has_permission_for_user(parse_account(account)[0], raise_exception=False):
				return cint(frappe.cache.get_value(_get_total_cache_key(account)))

		return 0

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
			validate_address_book_name_format(ab.address_book)
			_account, address_book_id = ab.address_book.split("|")
			ab.address_book_id = address_book_id


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Delete multiple Contact Cards based on their names."""

	if isinstance(names, str):
		names = json.loads(names)

	account_ids_map = {}
	for name in names:
		account, id = name.split("|")
		account_ids_map.setdefault(account, []).append(id)

	for account, ids in account_ids_map.items():
		delete_contact_cards(account, ids)

	frappe.msgprint(_("Contact Cards deleted successfully."), alert=True)


@frappe.whitelist()
def add_contact_card(
	account: str,
	address_book_ids: list[str],
	full_name: str | None = None,
	emails: list[dict] | None = None,
	phones: list[dict] | None = None,
	addresses: list[dict] | None = None,
	kind: str | None = None,
) -> str:
	"""Adds a contact card for the given account with the specified parameters."""

	has_permission_for_user(parse_account(account)[0])

	creation_id = str(uuid7())
	contact_card = {
		"creation_id": creation_id,
		"address_book_ids": address_book_ids,
		"full_name": full_name,
		"emails": emails,
		"phones": phones,
		"addresses": addresses,
		"kind": kind or "individual",
	}

	service = get_contact_card_service(account)
	response = service.create([contact_card])

	title = _("Contact Card Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def bulk_add_contact_cards(account: str, contact_cards: list[dict], raise_exception: bool = True) -> None:
	"""Adds multiple contact cards for the given account and returns their IDs."""

	has_permission_for_user(parse_account(account)[0])

	service = get_contact_card_service(account)

	for card in contact_cards:
		if not card.get("creation_id"):
			card["creation_id"] = str(uuid7())

	response = service.create(contact_cards)

	title = _("Contact Card Creation Error")
	if response.get("notCreated"):
		if raise_exception:
			frappe.throw(_("One or more contact cards failed to create"), title=title)


@frappe.whitelist()
def fetch_contact_cards(
	account: str,
	filter: dict | None = None,
	position: int = 0,
	limit: int = 50,
	sort: list[dict] | None = None,
) -> tuple[list[dict], int]:
	"""Returns a list of contact cards and total count based on the provided filter."""

	has_permission_for_user(parse_account(account)[0])

	contact_cards = []

	service = get_contact_card_service(account)
	data = service.query(filter, position, limit, sort)

	ids = data.get("ids", [])
	total = data.get("total", 0)

	contact_cards.extend(get_contact_cards(account, ids))

	return contact_cards[:limit], total


@frappe.whitelist()
def get_contact_cards(account: str, ids: list[str]) -> list[dict]:
	"""Returns a list of contact cards for the provided IDs in the same order as ids."""

	has_permission_for_user(parse_account(account)[0])

	contact_cards = {}
	ids_to_fetch = []

	for id in ids:
		if contact_card := _get_contact_card_from_cache(account, id):
			contact_cards[id] = contact_card
		else:
			ids_to_fetch.append(id)

	if ids_to_fetch:
		service = get_contact_card_service(account)
		cards = service.get(ids_to_fetch)

		address_book_map = {ab["id"]: ab["name"] for ab in service.address_books}

		for card in cards:
			contact_card = format_contact_card(account, address_book_map, card)
			_store_contact_card_in_cache(account, contact_card["id"], contact_card)
			contact_cards[contact_card["id"]] = contact_card

	return [contact_cards[id] for id in ids if id in contact_cards]


@frappe.whitelist()
def update_contact_card(
	account: str,
	id: str,
	address_book_ids: list[str],
	full_name: str | None = None,
	emails: list[dict] | None = None,
	phones: list[dict] | None = None,
	addresses: list[dict] | None = None,
	kind: str | None = None,
) -> None:
	"""Updates an existing contact card with the given parameters."""

	has_permission_for_user(parse_account(account)[0])

	contact_card = {
		"id": id,
		"address_book_ids": address_book_ids,
		"full_name": full_name,
		"emails": emails,
		"phones": phones,
		"addresses": addresses,
		"kind": kind or "individual",
	}

	service = get_contact_card_service(account)
	response = service.update([contact_card])

	title = _("Contact Card Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)

	_remove_contact_cards_from_cache(account, [id])


def contact_card_update_address_books(
	account: str,
	ids: list[str],
	add_address_book_id: str | None = None,
	remove_address_book_id: str | None = None,
	move_to_address_book_id: str | None = None,
) -> None:
	"""
	Updates addressBookIds for the provided contact cards.

	Behavior:
	- add_address_book_id: adds the contact to an address book
	- remove_address_book_id: removes the contact from an address book
	- add + remove: moves contact between address books (patch-based)
	- move_to_address_book_id: replaces addressBookIds entirely
	"""

	has_permission_for_user(parse_account(account)[0])

	service = get_contact_card_service(account)
	response = service.update_address_book_ids(
		ids, add_address_book_id, remove_address_book_id, move_to_address_book_id
	)

	title = _("Contact Card Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][ids[0]]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)

	_remove_contact_cards_from_cache(account, ids)


@frappe.whitelist()
def contact_card_add_to_address_book(account: str, ids: list[str], address_book_id: str) -> None:
	"""Adds the provided contact cards to an address book."""

	return contact_card_update_address_books(account, ids, add_address_book_id=address_book_id)


@frappe.whitelist()
def contact_card_remove_from_address_book(
	account: str,
	ids: list[str],
	address_book_id: str,
) -> None:
	"""Removes the provided contact cards from an address book."""

	return contact_card_update_address_books(account, ids, remove_address_book_id=address_book_id)


@frappe.whitelist()
def contact_card_move_between_address_books(
	account: str, ids: list[str], from_address_book_id: str, to_address_book_id: str
) -> None:
	"""Moves contact cards from one address book to another."""

	return contact_card_update_address_books(
		account,
		ids,
		add_address_book_id=to_address_book_id,
		remove_address_book_id=from_address_book_id,
	)


@frappe.whitelist()
def contact_card_move_to_address_book(
	account: str,
	ids: list[str],
	address_book_id: str,
) -> None:
	"""Moves contact cards to the given address book, replacing all others."""

	return contact_card_update_address_books(account, ids, move_to_address_book_id=address_book_id)


@frappe.whitelist()
def delete_contact_cards(account: str, ids: list[str]) -> None:
	"""Deletes contact cards for the given account by its IDs."""

	has_permission_for_user(parse_account(account)[0])

	service = get_contact_card_service(account)
	service.delete(ids)
	_remove_contact_cards_from_cache(account, ids)


def _get_contact_card_cache_key(account: str, id: str) -> str:
	"""Returns cache key for contact card."""

	return f"jmap:contact_card:{account}:{id}"


def _get_total_cache_key(account: str) -> str:
	"""Returns a cache key for total contact cards count for the given account."""

	return f"{account}:contact_cards:total"


def _get_contact_card_from_cache(account: str, id: str) -> dict | None:
	"""Returns contact card from cache if available."""

	cache_key = _get_contact_card_cache_key(account, id)
	return frappe.cache.get_value(cache_key)


def _remove_contact_cards_from_cache(account: str, ids: list[str]) -> None:
	"""Remove a contact cards from cache."""

	for id in ids:
		cache_key = _get_contact_card_cache_key(account, id)
		frappe.cache.delete_value(cache_key)

	list_key = f"jmap:contact_card:{account}:ids"
	for id in ids:
		frappe.cache.lrem(list_key, 0, id)

	if not frappe.cache.llen(list_key):
		frappe.cache.delete_value(list_key)


def _store_contact_card_in_cache(account: str, id: str, contact_card: dict) -> None:
	"""Store a contact card in cache with TTL and maintain per-account bucket size."""

	cache_key = _get_contact_card_cache_key(account, id)
	list_key = f"jmap:contact_card:{account}:ids"

	bucket_size = cint(get_mail_config("contact_card_bucket_size"))
	cache_ttl = cint(get_mail_config("contact_card_cache_ttl"))

	frappe.cache.set_value(cache_key, contact_card, expires_in_sec=cache_ttl)
	frappe.cache.lpush(list_key, id)

	frappe.cache.ltrim(list_key, 0, bucket_size - 1)

	while frappe.cache.llen(list_key) > bucket_size:
		if oldest_id := frappe.cache.rpop(list_key):
			frappe.cache.delete_key(_get_contact_card_cache_key(account, oldest_id))


def format_contact_card(account: str, address_book_map: dict, contact_card: dict) -> dict:
	"""Formats contact card data for display."""

	full_name = None
	if contact_name := contact_card.get("name"):
		if components := contact_name.get("components"):
			if contact_name.get("full"):
				full_name = contact_name["full"]
			elif contact_name.get("isOrdered", False):
				full_name = " ".join([component["value"] for component in components])
			else:
				given = next(
					(component["value"] for component in components if component["kind"] == "given"),
					"",
				)
				surname = next(
					(component["value"] for component in components if component["kind"] == "surname"),
					"",
				)
				full_name = f"{given} {surname}".strip()

	address_books = []
	for address_book_id in contact_card["addressBookIds"].keys():
		address_books.append(
			{
				"address_book": f"{account}|{address_book_id}",
				"address_book_id": address_book_id,
				"address_book_name": address_book_map.get(address_book_id),
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
				"label": email.get("label"),
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
				"label": phone.get("label"),
				"contexts": json.dumps(contexts, indent=4),
			}
		)

	addresses = []
	for address in contact_card.get("addresses", {}).values():
		time_zone = address.get("timeZone")
		contexts = address.get("contexts", {})
		component_map = {c["kind"]: c["value"] for c in address.get("components", [])}

		addresses.append(
			{
				"type": next(iter(contexts), None),
				"street": component_map.get("name"),
				"locality": component_map.get("locality"),
				"region": component_map.get("region"),
				"postcode": component_map.get("postcode"),
				"country": component_map.get("country"),
				"time_zone": time_zone,
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
		"uid": contact_card.get("uid"),
		"kind": contact_card.get("kind"),
		"name_breakup": json.dumps(contact_card.get("name", {}), indent=4),
		"full_name": full_name,
		"address_books": address_books,
		"emails": emails,
		"phones": phones,
		"addresses": addresses,
		"created_at": contact_card.get("created"),
		"updated_at": contact_card.get("updated"),
		"creation": creation or modified or today(),
		"modified": modified or creation or today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Contact Card":
		return False

	return has_permission_for_user(parse_account(doc.account)[0], raise_exception=False)
