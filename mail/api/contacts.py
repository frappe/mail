import frappe

from mail.client.doctype.address_book.address_book import fetch_address_books
from mail.client.doctype.contact_card.contact_card import fetch_contact_cards


@frappe.whitelist()
def get_address_books() -> list[str]:
	"""Returns the address books for the current user."""

	if not (address_books := fetch_address_books(frappe.session.user, 1, 50)):
		return []

	fields = ["name", "id", "_name", "default"]
	return [{f: d[f] for f in fields} for d in address_books]


@frappe.whitelist()
def get_contact_cards() -> list[str]:
	"""Returns the contact cards for the current user."""

	if not (contact_cards := fetch_contact_cards(frappe.session.user, None, 0, 500)[0]):
		return []

	fields = ["id", "full_name", "kind"]
	return [{f: d[f] for f in fields} for d in contact_cards]
