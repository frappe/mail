# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail.jmap import get_jmap_client
from mail.utils import parse_filters
from mail.utils.validation import has_permission_for_user


class Quota(Document):
	def db_insert(self, *args, **kwargs) -> None:
		raise NotImplementedError

	def load_from_db(self) -> "Quota":
		user, id = self.name.split("|")
		quota = get_quota(user, id)
		return super(Document, self).__init__(quota)

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
			frappe.msgprint(_("Please select a user to view quotas."), alert=True)
			return []

		quotas = []
		if id:
			if quota := get_quota(user, id, raise_exception=False):
				quotas.append(quota)
		else:
			quotas = fetch_quotas(user, limit=page_length)

		if not quotas:
			frappe.msgprint(_("No quotas found."), alert=True)

		return quotas

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
	"""Returns a cache key for total quota count for the given user."""

	return f"{user}:quotas:total"


@frappe.whitelist()
def get_quota(user: str, id: str, raise_exception: bool = True) -> dict | None:
	"""Returns quota details for the given name in the format 'user|id'."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	if quotas := client.quota_get([id]):
		return format_quota(user, quotas[0])

	if raise_exception:
		frappe.throw(
			_("Quota with ID {0} not found in user {1}.").format(frappe.bold(id), frappe.bold(user)),
			title=_("Quota Not Found"),
		)


@frappe.whitelist()
def fetch_quotas(user: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of quotas for the given user."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	quotas = client.quota_get()
	formatted_quotas = [format_quota(user, quota) for quota in quotas]
	frappe.cache.set_value(_get_total_cache_key(user), len(quotas), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_quotas[start:end]


def format_quota(user: str, quota: dict) -> dict:
	"""Formats quota data for display."""

	return {
		"name": f"{user}|{quota['id']}",
		"user": user,
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

	return has_permission_for_user(doc.user, raise_exception=False)
