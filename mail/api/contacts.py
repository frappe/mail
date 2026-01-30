import frappe

from mail.client.doctype.address_book.address_book import fetch_address_books
from mail.client.doctype.contact_card.contact_card import fetch_contact_cards


@frappe.whitelist()
def get_address_books() -> list[dict]:
	"""Returns the address books for the current user."""

	if not (address_books := fetch_address_books(frappe.session.user, 1, 50)):
		return []

	fields = ["name", "id", "_name", "default"]
	return [{f: d[f] for f in fields} for d in address_books]


@frappe.whitelist()
def get_contact_cards(filter: dict | None = None, limit: int = 50) -> list[dict]:
	"""Returns the contact cards for the current user."""

	if filter:
		filter = {k: v for k, v in filter.items() if v}

	if not (contact_cards := fetch_contact_cards(frappe.session.user, filter, 0, limit)[0]):
		return []

	fields = ["id", "full_name", "kind", "emails"]
	return [{f: d[f].capitalize() if f == "kind" else d[f] for f in fields} for d in contact_cards]


@frappe.whitelist()
def get_contacts(filter: dict | None = None, limit: int = 50) -> list[dict]:
	"""Returns the emails contacts for the current user."""

	contacts = []
	contact_cards = get_contact_cards(filter, limit)

	for card in contact_cards:
		if emails := card.get("emails"):
			for email in emails:
				contacts.append({"full_name": card.get("full_name"), "email": email.get("address")})

	return contacts
