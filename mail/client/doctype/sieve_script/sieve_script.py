# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from mail.jmap import get_sieve_script_service, parse_account
from mail.utils import parse_filters
from mail.utils.validation import has_permission_for_user


class SieveScript(Document):
	def db_insert(self, *args, **kwargs) -> None:
		self.id = SieveScript._add_sieve_script(self.account, self._name, self.content, bool(self.active))
		self.name = f"{self.account}|{self.id}"

	def load_from_db(self) -> "SieveScript":
		account, id = self.name.split("|")
		if scripts := SieveScript._get_sieve_scripts(account, [id], download_content=True):
			return super(Document, self).__init__(scripts[0])

		frappe.throw(
			_("Sieve Script with ID {0} not found in account {1}.").format(
				frappe.bold(id), frappe.bold(account)
			),
			title=_("Sieve Script Not Found"),
		)

	def db_update(self) -> None:
		SieveScript._update_sieve_script(self.account, self.id, self._name, self.content, bool(self.active))
		self.reload()

	def delete(self) -> None:
		account, id = self.name.split("|")

		if self.active:
			frappe.throw(_("Cannot delete an active sieve script. Please deactivate it first."))

		SieveScript._delete_sieve_scripts(account, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		id = filters.get("id")
		account = filters.get("account")

		if not account:
			frappe.msgprint(_("Please select an account to view the Sieve Scripts."), alert=True)
			return []

		scripts = []
		if id:
			scripts = SieveScript._get_sieve_scripts(account, [id])
			total = len(scripts)
		else:
			filter = {}
			if value := filters.get("_name"):
				filter["name"] = value
			if value := filters.get("active"):
				filter["isActive"] = bool(cint(value))

			limit = cint(kwargs.get("start")) + page_length
			scripts, total = SieveScript._fetch_sieve_scripts(account, filter, limit=limit)

		frappe.cache.set_value(_get_total_cache_key(account), total, expires_in_sec=600)

		if not scripts:
			frappe.msgprint(_("No sieve scripts found."), alert=True)

		return scripts

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

	@classmethod
	def _add_sieve_script(
		cls,
		account: str,
		name: str,
		content: str,
		active: bool = False,
	) -> str:
		"""Adds a sieve script for the given account with the specified parameters."""

		if not content or not content.strip():
			frappe.throw(_("Sieve script content cannot be empty."))

		user, _account_id = parse_account(account)
		has_permission_for_user(user)

		creation_id = str(uuid7())
		service = get_sieve_script_service(account)
		sieve_script = {
			"creation_id": creation_id,
			"name": name,
			"content": content,
			"is_active": active,
		}
		response = service.create([sieve_script])

		title = _("Sieve Script Creation Error")
		if response.get("created"):
			return response["created"][creation_id]["id"]
		elif response.get("notCreated"):
			frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)

	@classmethod
	def _fetch_sieve_scripts(
		cls,
		account: str,
		filter: dict | None = None,
		position: int = 0,
		limit: int = 50,
	) -> tuple[list, int]:
		"""Returns a list of sieve scripts for the given account."""

		user, _account_id = parse_account(account)
		has_permission_for_user(user)

		scripts = []

		service = get_sieve_script_service(account)
		data = service.query(filter, position, limit)

		ids = data.get("ids", [])
		total = data.get("total", 0)

		scripts.extend(SieveScript._get_sieve_scripts(account, ids))

		return scripts[:limit], total

	@classmethod
	def _get_sieve_scripts(cls, account: str, ids: list[str], download_content: bool = False) -> list[dict]:
		"""Returns a list of sieve scripts for the provided IDs in the same order as ids."""

		user, _account_id = parse_account(account)
		has_permission_for_user(user)

		sieve_scripts = {}

		service = get_sieve_script_service(account)
		scripts = service.get(ids)

		if download_content:
			blobs = [(s["blobId"], None) for s in scripts if s["blobId"]]
			data = service.download_blobs_concurrently(blobs)

			for script in scripts:
				script["content"] = data.get(script["blobId"], b"").decode("utf-8")

		for script in scripts:
			script = format_sieve_script(account, script)
			sieve_scripts[script["id"]] = script

		return [sieve_scripts[id] for id in ids if id in sieve_scripts]

	@classmethod
	def _validate_sieve_script(cls, account: str, content: str) -> None:
		"""Validates a sieve script for the given account."""

		if not content or not content.strip():
			frappe.throw(_("Sieve script content cannot be empty."))

		user, _account_id = parse_account(account)
		has_permission_for_user(user)

		service = get_sieve_script_service(account)
		response = service.validate(content)

		if error := response.get("error"):
			frappe.throw(
				_("{0}: {1}").format(error.get("type"), error.get("description")),
				title=_("Sieve Script Validation Error"),
			)

	@classmethod
	def _update_sieve_script(
		cls,
		account: str,
		id: str,
		name: str,
		content: str,
		active: bool = False,
	) -> None:
		"""Updates a sieve script for the given account and ID with the specified parameters."""

		if not content or not content.strip():
			frappe.throw(_("Sieve script content cannot be empty."))

		user, _account_id = parse_account(account)
		has_permission_for_user(user)

		service = get_sieve_script_service(account)
		scripts = service.get([id])

		if not scripts:
			frappe.throw(
				_("Sieve Script with ID {0} not found.").format(frappe.bold(id)),
				title=_("Sieve Script Not Found"),
			)

		script = scripts[0]
		deactivate = script["isActive"] and not active
		sieve_script = {"id": id, "name": name, "content": content, "is_active": bool(active)}
		response = service.update([sieve_script], deactivate=deactivate)

		title = _("Sieve Script Update Error")
		if not response.get("updated"):
			if response.get("notUpdated"):
				frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
			else:
				frappe.throw(_(response["description"]), title=title)

	@classmethod
	def _delete_sieve_scripts(cls, account: str, ids: list[str]) -> None:
		"""Deletes sieve scripts for the given list of IDs and account."""

		user, _account_id = parse_account(account)
		has_permission_for_user(user)

		service = get_sieve_script_service(account)
		response = service.delete(ids)

		if response.get("notDestroyed"):
			error_messages = []
			for id, error in response["notDestroyed"].items():
				error_messages.append(f"{id}: {error['description']}")
			frappe.throw(
				_("Sieve Script Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
				title=_("Sieve Script Deletion Error"),
			)

	def validate(self) -> None:
		if self.read_only:
			frappe.throw(
				_("The '{0}' sieve script cannot be modified.").format(self._name),
				title=_("Read-Only Sieve Script"),
			)

	@frappe.whitelist()
	def validate_script(self) -> None:
		"""Validates the sieve script content."""

		account, _id = self.name.split("|")
		user, _account_id = parse_account(account)
		has_permission_for_user(user)

		self._validate_sieve_script(account, self.content)
		frappe.msgprint(_("Sieve script is valid."), indicator="green", alert=True)


def _get_total_cache_key(account: str) -> str:
	"""Returns a cache key for total sieve scripts count for the given account."""

	return f"{account}:sieve_scripts:total"


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes multiple sieve scripts given their names."""

	if isinstance(names, str):
		names = json.loads(names)

	account_ids_map = {}
	for name in names:
		account, id = name.split("|")
		account_ids_map.setdefault(account, []).append(id)

	for account, ids in account_ids_map.items():
		SieveScript._delete_sieve_scripts(account, ids)

	frappe.msgprint(_("Sieve Scripts deleted successfully."), alert=True)


def get_active_sieve_script_id(account: str) -> str | None:
	"""Returns the ID of the currently active sieve script for the given account, if any."""

	service = get_sieve_script_service(account)
	query_result = service.query({"isActive": True})

	if query_result.get("ids") and len(query_result["ids"]) > 0:
		return query_result["ids"][0]


def activate_last_active_sieve_script(account: str) -> None:
	"""Activates the last active sieve script for the given account, if any, and clears the last active sieve script setting."""

	sieve_script_id = frappe.db.get_value(
		"Account Settings", {"account": account}, "last_active_sieve_script_id"
	)
	if not sieve_script_id:
		return

	if sieve_scripts := SieveScript._get_sieve_scripts(account, [sieve_script_id], download_content=True):
		sieve_script = sieve_scripts[0]

		if (sieve_script.get("_name") or "").lower() != "vacation" and not sieve_script["active"]:
			SieveScript._update_sieve_script(
				account,
				sieve_script_id,
				sieve_script["_name"],
				sieve_script["content"],
				active=True,
			)

	set_last_active_sieve_script_id(account, None)


def set_last_active_sieve_script_id(account: str, sieve_script_id: str | None = None) -> None:
	"""Sets the given sieve script ID as the last active sieve script for the given account."""

	frappe.db.set_value(
		"Account Settings",
		{"account": account},
		"last_active_sieve_script_id",
		sieve_script_id,
		update_modified=False,
	)


def format_sieve_script(account: str, script: dict) -> dict:
	"""Format the sieve script for display."""

	read_only = script["name"].lower() == "vacation"

	return {
		"name": f"{account}|{script['id']}",
		"account": account,
		"id": script["id"],
		"_name": script["name"],
		"active": cint(script["isActive"]),
		"blob_id": script["blobId"],
		"content": script.get("content") or "",
		"read_only": read_only,
		"creation": today(),
		"modified": today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Sieve Script":
		return False

	doc_user, _account_id = parse_account(doc.account)

	return has_permission_for_user(doc_user, raise_exception=False)
