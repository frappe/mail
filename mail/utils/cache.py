import frappe
from typing import Any


def _get_or_set(
	name: str, getter: callable, expires_in_sec: int | None = 60 * 60
) -> Any | None:
	"""Get or set a value in the cache."""

	value = frappe.cache.get_value(name)

	if not value:
		value = getter()
		frappe.cache.set_value(name, value, expires_in_sec=expires_in_sec)

	if isinstance(value, bytes):
		value = value.decode()

	return value


def _hget_or_hset(name: str, key: str, getter: callable) -> Any | None:
	"""Get or set a value in the cache hash."""

	value = frappe.cache.hget(name, key)

	if not value:
		value = getter()
		frappe.cache.hset(name, key, value)

	return value


def delete_cache(name: str, key: str | None = None) -> None:
	"""Delete a value from the cache."""

	if not key:
		frappe.cache.delete_value(name)
	else:
		frappe.cache.hdel(name, key)


def get_root_domain_name() -> str | None:
	"""Returns the root domain name."""

	def getter() -> str | None:
		return frappe.db.get_single_value("Mail Settings", "root_domain_name")

	return _get_or_set("root_domain_name", getter, expires_in_sec=None)


def get_postmaster() -> str:
	"""Returns the postmaster."""

	def getter() -> str:
		return frappe.db.get_single_value("Mail Settings", "postmaster") or "Administrator"

	return _get_or_set("postmaster", getter, expires_in_sec=None)


def get_incoming_mail_agents() -> list:
	"""Returns the incoming mail agents."""

	def getter() -> list:
		MA = frappe.qb.DocType("Mail Agent")
		return (
			frappe.qb.from_(MA).select(MA.name).where((MA.enabled == 1) & (MA.incoming == 1))
		).run(pluck="name")

	return _get_or_set("incoming_mail_agents", getter)


def get_outgoing_mail_agents() -> list:
	"""Returns the outgoing mail agents."""

	def getter() -> list:
		MA = frappe.qb.DocType("Mail Agent")
		return (
			frappe.qb.from_(MA).select(MA.name).where((MA.enabled == 1) & (MA.outgoing == 1))
		).run(pluck="name")

	return _get_or_set("outgoing_mail_agents", getter)


def get_user_domains(user: str) -> list:
	"""Returns the domains of the user."""

	def getter() -> list:
		MAILBOX = frappe.qb.DocType("Mailbox")
		return (
			frappe.qb.from_(MAILBOX)
			.select("domain_name")
			.where((MAILBOX.user == user) & (MAILBOX.enabled == 1))
			.distinct()
		).run(pluck="domain_name")

	return _hget_or_hset(f"user|{user}", "domains", getter)


def get_user_owned_domains(user: str) -> list:
	"""Returns the domains owned by the user."""

	def getter() -> list:
		MAIL_DOMAIN = frappe.qb.DocType("Mail Domain")
		return (
			frappe.qb.from_(MAIL_DOMAIN)
			.select("name")
			.where((MAIL_DOMAIN.enabled == 1) & (MAIL_DOMAIN.domain_owner == user))
		).run(pluck="name")

	return _hget_or_hset(f"user|{user}", "owned_domains", getter)


def get_user_incoming_mailboxes(user: str) -> list:
	"""Returns the incoming mailboxes of the user."""

	def getter() -> list:
		MAILBOX = frappe.qb.DocType("Mailbox")
		return (
			frappe.qb.from_(MAILBOX)
			.select("name")
			.where((MAILBOX.user == user) & (MAILBOX.enabled == 1) & (MAILBOX.incoming == 1))
		).run(pluck="name")

	return _hget_or_hset(f"user|{user}", "incoming_mailboxes", getter)


def get_user_outgoing_mailboxes(user: str) -> list:
	"""Returns the outgoing mailboxes of the user."""

	def getter() -> list:
		MAILBOX = frappe.qb.DocType("Mailbox")
		return (
			frappe.qb.from_(MAILBOX)
			.select("name")
			.where((MAILBOX.user == user) & (MAILBOX.enabled == 1) & (MAILBOX.outgoing == 1))
		).run(pluck="name")

	return _hget_or_hset(f"user|{user}", "outgoing_mailboxes", getter)


def get_user_default_mailbox(user: str) -> str | None:
	"""Returns the default mailbox of the user."""

	def getter() -> str | None:
		return frappe.db.get_value("Mailbox", {"user": user, "is_default": 1}, "name")

	return _hget_or_hset(f"user|{user}", "default_mailbox", getter)
