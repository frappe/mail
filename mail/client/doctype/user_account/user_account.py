# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from mail.jmap import get_jmap_connection
from mail.utils import parse_filters
from mail.utils.validation import has_permission_for_user


class UserAccount(Document):
	def db_insert(self, *args, **kwargs) -> None:
		raise NotImplementedError

	def load_from_db(self) -> "UserAccount":
		user, id = self.name.split(":")
		account = get_user_account(user, id)
		return super(Document, self).__init__(account)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		raise NotImplementedError

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		id = filters.get("id")
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view accounts."), alert=True)
			return []

		accounts = []
		if id:
			if account := get_user_account(user, id, raise_exception=False):
				accounts.append(account)
		else:
			accounts = fetch_user_accounts(user, limit=page_length)

		if not accounts:
			frappe.msgprint(_("No accounts found."), alert=True)

		return accounts

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user
		return (
			frappe.cache.get_value(_get_total_cache_key(user))
			if user and has_permission_for_user(user, raise_exception=False)
			else 0
		)

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}


def _get_total_cache_key(user: str) -> str:
	"""Returns a cache key for total account count for the given user."""

	return f"{user}:accounts:total"


@frappe.whitelist()
def get_user_account(user: str, id: str, raise_exception: bool = False) -> dict | None:
	"""Returns the account with the specified ID for the given user, or None if not found."""

	has_permission_for_user(user)

	for account in fetch_user_accounts(user, limit=None):
		if account["id"] == id:
			return account

	if raise_exception:
		frappe.throw(
			_("Account with ID '{0}' not found for user '{1}'.").format(id, user), frappe.DoesNotExistError
		)


@frappe.whitelist()
def fetch_user_accounts(user: str, page: int = 1, limit: int | None = 10) -> list:
	"""Fetches accounts for the specified user, with pagination."""

	connection = get_jmap_connection(user)
	accounts = [{"id": id, **details} for id, details in connection.accounts.items()]
	formatted_accounts = [format_user_account(user, account) for account in accounts]
	sorted_accounts = sorted(formatted_accounts, key=lambda a: (a["name"], a["id"]))
	frappe.cache.set_value(_get_total_cache_key(user), len(accounts), expires_in_sec=600)

	if limit is None:
		return sorted_accounts

	start = (page - 1) * limit
	end = start + limit

	return sorted_accounts[start:end]


def format_user_account(user: str, account: dict) -> dict:
	"""Formats account data for display."""

	return {
		"name": f"{user}:{account['id']}",
		"user": user,
		"id": account["id"],
		"_name": account["name"],
		"is_personal": cint(account.get("isPersonal", False)),
		"is_read_only": cint(account.get("isReadOnly", False)),
		"capabilities": json.dumps(account.get("accountCapabilities") or {}, indent=4),
		"creation": today(),
		"modified": today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "User Account":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
