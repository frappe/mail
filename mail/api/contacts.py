import json
import re

import frappe

from mail.client.doctype.address_book.address_book import fetch_address_books
from mail.client.doctype.contact_card.contact_card import bulk_add_contact_cards, fetch_contact_cards
from mail.jmap import get_default_address_book_id


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
	return [{f: d[f].capitalize() if f == "kind" and d[f] else d[f] for f in fields} for d in contact_cards]


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


@frappe.whitelist()
def get_address_book_contact_count(address_book) -> int:
	"""Returns the total no. of contacts for the fiven address book."""

	return fetch_contact_cards(frappe.session.user, {"inAddressBook": address_book}, 0, 1)[1]


def create_contacts_if_not_exists(recipients: list[dict] | str) -> None:
	"""Creates contacts for the given recipients if they do not exist."""

	user = frappe.session.user
	if not frappe.db.get_value("User Settings", user, "create_contacts_after_email_submit"):
		return

	if isinstance(recipients, str):
		recipients = json.loads(recipients)

	emails = set([recipient.get("email") for recipient in recipients if recipient.get("email")])

	new_emails = []
	for email in emails:
		if not (fetch_contact_cards(user, {"email": email}, 0, 1)[0]):
			new_emails.append(email)

	contact_cards = []
	for email in new_emails:
		contact_card = {
			"user": user,
			"address_book_ids": [get_default_address_book_id(user)],
			"full_name": extract_name_from_email(email),
			"kind": "Individual",
			"emails": [{"address": email, "type": "Personal"}],
		}
		contact_cards.append(contact_card)

	bulk_add_contact_cards(user, contact_cards)


def extract_name_from_email(email: str) -> str:
	"""Extracts a name from the given email address."""

	return re.sub(r"\b\w", lambda m: m.group().upper(), re.sub(r"[._-]", " ", email.split("@")[0]))
