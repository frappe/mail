# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.jmap import get_quota_service, parse_account
from mail.utils import parse_filters
from mail.utils.validation import has_permission_for_user


class Quota(Document):
	def db_insert(self, *args, **kwargs) -> None:
		raise NotImplementedError

	def load_from_db(self) -> "Quota":
		account, id = self.name.split("|")
		quota = get_quota(account, id)
		return super(Document, self).__init__(quota)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		raise NotImplementedError

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		id = filters.get("id")
		account = filters.get("account")

		if not account:
			frappe.msgprint(_("Please select an account to view quotas."), alert=True)
			return []

		quotas = []
		if id:
			if quota := get_quota(account, id, raise_exception=False):
				quotas.append(quota)
		else:
			quotas = fetch_quotas(account, limit=page_length)

		if not quotas:
			frappe.msgprint(_("No quotas found."), alert=True)

		return quotas

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		account = filters.get("account")

		if account:
			user, _account_id = parse_account(account)

			if has_permission_for_user(user, raise_exception=False):
				return cint(frappe.cache.get_value(_get_total_cache_key(account)))

		return 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}


def _get_total_cache_key(account: str) -> str:
	"""Returns a cache key for total quota count for the given account."""

	return f"{account}:quotas:total"


@frappe.whitelist()
def get_quota(account: str, id: str, raise_exception: bool = True) -> dict | None:
	"""Returns quota details for the given name in the format 'account|id'."""

	user, _account_id = parse_account(account)
	has_permission_for_user(user)

	service = get_quota_service(account)

	if quotas := service.get([id]):
		return format_quota(account, quotas[0])

	if raise_exception:
		frappe.throw(
			_("Quota with ID {0} not found in account {1}.").format(frappe.bold(id), frappe.bold(account)),
			title=_("Quota Not Found"),
		)


@frappe.whitelist()
def fetch_quotas(account: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of quotas for the given account."""

	user, _account_id = parse_account(account)
	has_permission_for_user(user)

	service = get_quota_service(account)
	quotas = service.get()
	formatted_quotas = [format_quota(account, quota) for quota in quotas]
	frappe.cache.set_value(_get_total_cache_key(account), len(quotas), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_quotas[start:end]


def format_quota(account: str, quota: dict) -> dict:
	"""Formats quota data for display."""

	return {
		"name": f"{account}|{quota['id']}",
		"account": account,
		"id": quota["id"],
		"_name": quota["name"],
		"resource_type": quota["resourceType"],
		"used": cint(quota["used"]),
		"warn_limit": cint(quota["warnLimit"]),
		"soft_limit": cint(quota["softLimit"]),
		"hard_limit": cint(quota["hardLimit"]),
		"scope": quota["scope"],
		"description": quota["description"],
		"types": json.dumps(quota.get("types", []), indent=4, sort_keys=True),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Quota":
		return False

	doc_user, _account_id = parse_account(doc.account)

	return has_permission_for_user(doc_user, raise_exception=False)
