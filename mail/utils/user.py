import frappe
from typing import Literal


def is_system_manager(user: str) -> bool:
	"""Returns True if the user is Administrator or System Manager else False."""

	return user == "Administrator" or has_role(user, "System Manager")


def is_postmaster(user: str) -> bool:
	"""Returns True if the user is Postmaster else False."""

	return user == get_postmaster()


def get_user_mailboxes(
	user: str, type: Literal["Incoming", "Outgoing"] | None = None
) -> list:
	"""Returns the list of mailboxes associated with the user."""

	MAILBOX = frappe.qb.DocType("Mailbox")
	query = frappe.qb.from_(MAILBOX).select("name").where(MAILBOX.user == user)

	if type:
		query.where(MAILBOX[type.lower()] == 1)

	return query.run(pluck="name")


def is_mailbox_owner(mailbox: str, user: str) -> bool:
	"""Returns True if the mailbox is associated with the user else False."""

	return frappe.get_cached_value("Mailbox", mailbox, "user") == user


def get_user_domains(user: str) -> list:
	"""Returns the list of domains associated with the user's mailboxes."""

	return list(
		set(frappe.db.get_all("Mailbox", filters={"user": user}, pluck="domain_name"))
	)


def get_user_owned_domains(user: str) -> list:
	"""Returns the list of domains owned by the user."""

	return frappe.db.get_all(
		"Mail Domain", filters={"domain_owner": user}, pluck="domain_name"
	)


def has_role(user: str, roles: str | list) -> bool:
	"""Returns True if the user has any of the given roles else False."""

	if isinstance(roles, str):
		roles = [roles]

	user_roles = frappe.get_roles(user)
	for role in roles:
		if role in user_roles:
			return True

	return False


def get_postmaster() -> str:
	"""Returns the Postmaster from Mail Settings."""

	return (
		frappe.db.get_single_value("Mail Settings", "postmaster", cache=True)
		or "Administrator"
	)
