import frappe

from mail.client.doctype.address_book.address_book import fetch_address_books
from mail.client.doctype.mailbox.mailbox import fetch_mailboxes


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_users_with_mail_admin_role(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of User(s) who have Mail Admin role."""

	USER = frappe.qb.DocType("User")
	HAS_ROLE = frappe.qb.DocType("Has Role")
	return (
		frappe.qb.from_(USER)
		.left_join(HAS_ROLE)
		.on(USER.name == HAS_ROLE.parent)
		.select(USER.name)
		.where(
			(USER.enabled == 1)
			& (USER.name.like(f"%{txt}%"))
			& (HAS_ROLE.role == "Mail Admin")
			& (HAS_ROLE.parenttype == "User")
		)
	).run(as_dict=False)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_users_with_mail_user_role(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of users with Mail User role."""

	USER = frappe.qb.DocType("User")
	HAS_ROLE = frappe.qb.DocType("Has Role")
	return (
		frappe.qb.from_(USER)
		.left_join(HAS_ROLE)
		.on(USER.name == HAS_ROLE.parent)
		.select(USER.name)
		.where(
			(USER.enabled == 1)
			& (USER.name.like(f"%{txt}%"))
			& (HAS_ROLE.role == "Mail User")
			& (HAS_ROLE.parenttype == "User")
		)
	).run(as_dict=False)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_personal_signup_domains(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of Mail Domains that allow personal signup."""

	MAIL_DOMAIN = frappe.qb.DocType("Mail Domain")
	MAIL_TENANT = frappe.qb.DocType("Mail Tenant")
	return (
		frappe.qb.from_(MAIL_DOMAIN)
		.left_join(MAIL_TENANT)
		.on(MAIL_DOMAIN.tenant == MAIL_TENANT.name)
		.select(MAIL_DOMAIN.name)
		.where(
			(MAIL_DOMAIN.enabled == 1)
			& (MAIL_DOMAIN.is_verified == 1)
			& (MAIL_DOMAIN.name.like(f"%{txt}%"))
			& (MAIL_TENANT.allow_personal_signup == 1)
		)
	).run(as_dict=False)


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
			if txt and txt.lower() not in mailbox["id"].lower():
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
			if txt and txt.lower() not in address_book["id"].lower():
				continue

			result.append([address_book["name"]])

	return result[start : start + page_len]
