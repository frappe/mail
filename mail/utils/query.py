import frappe

from mail.client.doctype.address_book.address_book import fetch_address_books
from mail.client.doctype.calendar.calendar import fetch_calendars
from mail.client.doctype.mailbox.mailbox import fetch_mailboxes
from mail.client.doctype.user_account.user_account import fetch_user_accounts


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_user_accounts(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of accounts for the user."""

	filters = filters or {}
	user = filters.get("user") or frappe.session.user

	if not user or user in ("Guest", "Administrator"):
		return []

	result = []
	if user_accounts := fetch_user_accounts(user):
		for account in user_accounts:
			if txt and txt.lower() not in account["name"].lower():
				continue

			result.append([account["name"]])

	return result[start : start + page_len]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_account_mailboxes(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of mailboxes for the account."""

	filters = filters or {}
	account = filters.get("account")

	if not account:
		return []

	result = []
	if mailboxes := fetch_mailboxes(account):
		for mailbox in mailboxes:
			if txt and txt.lower() not in mailbox["name"].lower():
				continue

			result.append([mailbox["name"]])

	return result[start : start + page_len]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_account_address_books(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of address books for the account."""

	filters = filters or {}
	account = filters.get("account")

	if not account:
		return []

	result = []
	if address_books := fetch_address_books(account):
		for address_book in address_books:
			if txt and txt.lower() not in address_book["name"].lower():
				continue

			result.append([address_book["name"]])

	return result[start : start + page_len]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_account_calendars(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of calendars for the account."""

	filters = filters or {}
	account = filters.get("account")

	if not account:
		return []

	result = []
	if calendars := fetch_calendars(account):
		for calendar in calendars:
			if txt and txt.lower() not in calendar["name"].lower():
				continue

			result.append([calendar["name"]])

	return result[start : start + page_len]
