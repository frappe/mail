# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today
from uuid_utils import uuid7

from mail.client.doctype.address_book.address_book import validate_address_book_name_format
from mail.jmap import get_jmap_client_for_user
from mail.utils import parse_filters
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
					}
				)

			return addresses

	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_contact_card(
			self.user,
			self.address_book_ids,
			self.full_name,
			self.formatted_emails,
			self.formatted_phones,
			self.formatted_addresses,
			self.kind,
		)
		self.name = f"{self.user}|{self.id}"

	def load_from_db(self) -> "ContactCard":
		user, id = self.name.split("|")
		if contact_cards := get_contact_cards(user, id):
			return super(Document, self).__init__(contact_cards[0])

		frappe.throw(
			_("Contact Card with ID {0} not found in user {1}.").format(frappe.bold(id), frappe.bold(user)),
			title=_("Contact Card Not Found"),
		)

	def db_update(self) -> None:
		update_contact_card(
			self.user,
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
		user, id = self.name.split("|")
		delete_contact_cards(user, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)

		user = filters.get("user")
		address_book = filters.get("address_book")
		if address_book:
			validate_address_book_name_format(address_book)

			if user and user != address_book.split("|")[0]:
				frappe.throw(
					_("Address Book {0} does not belong to User {1}.").format(
						frappe.bold(address_book), frappe.bold(user)
					)
				)

			user, address_book_id = address_book.split("|")
		else:
			user = user or frappe.session.user
			address_book_id = None

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view contact cards."), alert=True)
			return []

		filter = {}
		if address_book_id:
			filter["inAddressBook"] = address_book_id
		limit = cint(kwargs.get("start")) + page_length
		contact_cards, total = fetch_contact_cards(user, filter, limit=limit)
		frappe.cache.set_value(_get_total_cache_key(user), total, expires_in_sec=600)

		if not contact_cards:
			frappe.msgprint(_("No contact card found."), alert=True)

		return contact_cards

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
		self.validate_address_books()

	def validate_address_books(self) -> None:
		"""Validates that at least one address book is associated with the contact card."""

		if not self.address_books:
			frappe.throw(_("A contact card must belong to at least one address book."))

		for ab in self.address_books:
			validate_address_book_name_format(ab.address_book)
			_user, address_book_id = ab.address_book.split("|")
			ab.address_book_id = address_book_id


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Delete multiple Contact Cards based on their names."""

	if isinstance(names, str):
		names = json.loads(names)

	user_ids_map = {}
	for name in names:
		user, id = name.split("|")
		user_ids_map.setdefault(user, []).append(id)

	for user, ids in user_ids_map.items():
		delete_contact_cards(user, ids)

	frappe.msgprint(_("Contact Cards deleted successfully."), alert=True)


def add_contact_card(
	user: str,
	address_book_ids: list[str],
	full_name: str | None = None,
	emails: list[dict] | None = None,
	phones: list[dict] | None = None,
	addresses: list[dict] | None = None,
	kind: str = "individual",
) -> str:
	"""Adds a contact card for the given user with the specified parameters."""

	has_permission_for_user(user)

	creation_id = str(uuid7())
	client = get_jmap_client_for_user(user)
	response = client.contact_card_create(
		creation_id, address_book_ids, full_name, emails, phones, addresses, kind
	)

	title = _("Contact Card Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


def fetch_contact_cards(
	user: str,
	filter: dict | None = None,
	position: int = 0,
	limit: int = 50,
	sort: list[dict] | None = None,
) -> tuple[list[dict], int]:
	"""Returns a list of contact cards and total count based on the provided filter."""

	has_permission_for_user(user)

	contact_cards = []
	client = get_jmap_client_for_user(user)

	while len(contact_cards) < limit:
		result = client.contact_card_query(filter, position, limit, sort)
		ids = result["ids"]
		total = result["total"]

		if not ids:
			break

		contact_cards.extend(get_contact_cards(user, ids))

		if len(contact_cards) >= limit:
			break

		position += len(ids)

		if position >= total:
			break

	return contact_cards[:limit], total


def get_contact_cards(user: str, ids: list[str]) -> list[dict]:
	"""Returns a list of contact cards for the provided IDs in the same order as ids."""

	has_permission_for_user(user)

	contact_cards = {}
	ids_to_fetch = []

	for id in ids:
		if contact_card := _get_contact_card_from_cache(user, id):
			contact_cards[id] = contact_card
		else:
			ids_to_fetch.append(id)

	if ids_to_fetch:
		client = get_jmap_client_for_user(user)
		cards = client.contact_card_get(ids_to_fetch)

		address_book_map = {ab["id"]: ab["_name"] for ab in client.address_books}

		for card in cards:
			contact_card = format_contact_card(user, address_book_map, card)
			_store_contact_card_in_cache(user, contact_card["id"], contact_card)
			contact_cards[contact_card["id"]] = contact_card

	return [contact_cards[id] for id in ids if id in contact_cards]


def update_contact_card(
	user: str,
	id: str,
	address_book_ids: list[str],
	full_name: str | None = None,
	emails: list[dict] | None = None,
	phones: list[dict] | None = None,
	addresses: list[dict] | None = None,
	kind: str = "individual",
) -> None:
	"""Updates an existing contact card with the given parameters."""

	has_permission_for_user(user)

	client = get_jmap_client_for_user(user)
	response = client.contact_card_update(id, address_book_ids, full_name, emails, phones, addresses, kind)

	title = _("Contact Card Update Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)

	_remove_contact_cards_from_cache(user, [id])


def delete_contact_cards(user: str, ids: list[str]) -> None:
	"""Deletes contact cards for the given user by its IDs."""

	has_permission_for_user(user)

	client = get_jmap_client_for_user(user)
	client.contact_card_delete(ids)
	_remove_contact_cards_from_cache(user, ids)


def _get_contact_card_cache_key(user: str, id: str) -> str:
	"""Returns cache key for contact card."""

	return f"jmap:contact_card:{user}:{id}"


def _get_total_cache_key(user: str) -> str:
	"""Returns a cache key for total contact cards count for the given user."""

	return f"{user}:contact_cards:total"


def _get_contact_card_from_cache(user: str, id: str) -> dict | None:
	"""Returns contact card from cache if available."""

	cache_key = _get_contact_card_cache_key(user, id)
	return frappe.cache.get_value(cache_key)


def _remove_contact_cards_from_cache(user: str, ids: list[str]) -> None:
	"""Remove a contact cards from cache."""

	for id in ids:
		cache_key = _get_contact_card_cache_key(user, id)
		frappe.cache.delete_value(cache_key)

	list_key = f"jmap:contact_card:{user}:ids"
	for id in ids:
		frappe.cache.lrem(list_key, 0, id)

	if not frappe.cache.llen(list_key):
		frappe.cache.delete_value(list_key)


def _store_contact_card_in_cache(user: str, id: str, contact_card: dict) -> None:
	"""Store a contact card in cache with TTL and maintain per-user bucket size."""

	cache_key = _get_contact_card_cache_key(user, id)
	list_key = f"jmap:contact_card:{user}:ids"
	contact_card_bucket_size = cint(frappe.conf.contact_card_bucket_size) or 5000

	contact_card_cache_ttl = cint(frappe.conf.contact_card_cache_ttl) or 2 * 24 * 60 * 60  # 2 days
	frappe.cache.set_value(cache_key, contact_card, expires_in_sec=contact_card_cache_ttl)
	frappe.cache.lpush(list_key, id)

	frappe.cache.ltrim(list_key, 0, contact_card_bucket_size - 1)

	while frappe.cache.llen(list_key) > contact_card_bucket_size:
		if oldest_id := frappe.cache.rpop(list_key):
			frappe.cache.delete_key(_get_contact_card_cache_key(user, oldest_id))


def format_contact_card(user: str, address_book_map: dict, contact_card: dict) -> dict:
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
				"address_book": f"{user}|{address_book_id}",
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
		contexts = address.get("contexts", {})
		type = next(context for context in contexts.keys()) if contexts else None

		street = None
		if _street := address.get("street"):
			if isinstance(_street, dict):
				components = _street.get("components", [])
				street = next(
					(component["value"] for component in components if component["kind"] == "name"), None
				)
			elif isinstance(_street, str):
				street = _street

		addresses.append(
			{
				"type": type,
				"street": street,
				"locality": address.get("locality"),
				"region": address.get("region"),
				"country": address.get("country"),
				"postcode": address.get("postcode"),
				"contexts": json.dumps(contexts, indent=4),
			}
		)

	creation = modified = None
	if contact_card.get("created"):
		creation = parse_iso_datetime(contact_card["created"], as_str=True)
	if contact_card.get("updated"):
		modified = parse_iso_datetime(contact_card["updated"], as_str=True)

	return {
		"name": f"{user}|{contact_card['id']}",
		"user": user,
		"id": contact_card["id"],
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

	return has_permission_for_user(doc.user, raise_exception=False)
