import frappe

from mail.client.doctype.address_book.address_book import fetch_address_books


@frappe.whitelist()
def get_address_books() -> list[str]:
	"""Returns the address books for the current user."""

	if not (address_books := fetch_address_books(frappe.session.user, 1, 50)):
		return []

	fields = ["id", "_name", "default"]
	return [{f: d[f] for f in fields} for d in address_books]


@frappe.whitelist()
def get_contact_cards() -> list[str]:
	"""Returns the contact cards for the current user."""

	contact_cards = frappe.get_list("Contact Card", filters={"user": frappe.session.user})

	fields = ["name", "full_name", "kind"]
	return [{f: d[f] for f in fields} for d in contact_cards]
