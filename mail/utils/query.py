import frappe

from mail.client.doctype.address_book.address_book import fetch_address_books
from mail.client.doctype.mailbox.mailbox import fetch_mailboxes


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_tenant_users(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of users for the tenant."""

	filters = filters or {}
	tenant = filters.get("tenant")
	if not tenant:
		return []

	TENANT_MEMBER = frappe.qb.DocType("Mail Tenant Member")
	return (
		frappe.qb.from_(TENANT_MEMBER)
		.select(TENANT_MEMBER.name, TENANT_MEMBER.user)
		.where((TENANT_MEMBER.tenant == tenant) & (TENANT_MEMBER.user.like(f"%{txt}%")))
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
	"""Returns a list of Domains that allow personal signup."""

	TENANT = frappe.qb.DocType("Mail Tenant")
	PRINCIPAL_BINDING = frappe.qb.DocType("Mail Principal Binding")
	return (
		frappe.qb.from_(PRINCIPAL_BINDING)
		.left_join(TENANT)
		.on(PRINCIPAL_BINDING.tenant == TENANT.name)
		.select(PRINCIPAL_BINDING.name, PRINCIPAL_BINDING.principal_name)
		.where(
			(PRINCIPAL_BINDING.is_verified == 1)
			& (PRINCIPAL_BINDING.principal_type == "Domain")
			& (PRINCIPAL_BINDING.principal_name.like(f"%{txt}%"))
			& (TENANT.allow_personal_signup == 1)
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
