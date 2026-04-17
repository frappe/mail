import frappe

from mail.client.doctype.address_book.address_book import fetch_address_books
from mail.client.doctype.calendar.calendar import fetch_calendars
from mail.client.doctype.mailbox.mailbox import fetch_mailboxes


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_user_mailboxes(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of mailboxes for the user."""

	filters = filters or {}
	user = filters.get("user") or frappe.session.user

	if not user or user in ("Guest", "Administrator"):
		return []

	result = []
	if mailboxes := fetch_mailboxes(user):
		for mailbox in mailboxes:
			if txt and txt.lower() not in mailbox["name"].lower():
				continue

			result.append([mailbox["name"]])

	return result[start : start + page_len]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_user_address_books(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of address books for the user."""

	filters = filters or {}
	user = filters.get("user") or frappe.session.user

	if not user or user in ("Guest", "Administrator"):
		return []

	result = []
	if address_books := fetch_address_books(user):
		for address_book in address_books:
			if txt and txt.lower() not in address_book["name"].lower():
				continue

			result.append([address_book["name"]])

	return result[start : start + page_len]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_user_calendars(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of calendars for the user."""

	filters = filters or {}
	user = filters.get("user") or frappe.session.user

	if not user or user in ("Guest", "Administrator"):
		return []

	result = []
	if calendars := fetch_calendars(user):
		for calendar in calendars:
			if txt and txt.lower() not in calendar["name"].lower():
				continue

			result.append([calendar["name"]])

	return result[start : start + page_len]
