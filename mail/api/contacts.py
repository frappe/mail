import frappe

from mail.client.doctype.address_book.address_book import fetch_address_books


@frappe.whitelist()
def get_address_books() -> list[str]:
	"""Returns the address books for the current user."""

	if not (address_books := fetch_address_books(frappe.session.user, 1, 50)):
		return []

	fields = ["name", "_name", "default"]
	return [{f: d[f] for f in fields} for d in address_books]
