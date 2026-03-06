# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from mail.jmap import get_jmap_client
from mail.utils import parse_filters
from mail.utils.validation import has_permission_for_user


class SieveScript(Document):
	def db_insert(self, *args, **kwargs) -> None:
		self.id = SieveScript._add_sieve_script(self.user, self._name, self.content, bool(self.active))
		self.name = f"{self.user}|{self.id}"

	def load_from_db(self) -> "SieveScript":
		user, id = self.name.split("|")
		frappe.flags.download_sieve_script_content = True
		if scripts := SieveScript._get_sieve_scripts(user, [id]):
			return super(Document, self).__init__(scripts[0])

		frappe.throw(
			_("Sieve Script with ID {0} not found in user {1}.").format(frappe.bold(id), frappe.bold(user)),
			title=_("Sieve Script Not Found"),
		)

	def db_update(self) -> None:
		SieveScript._update_sieve_script(self.user, self.id, self._name, self.content, bool(self.active))
		self.reload()

	def delete(self) -> None:
		user, id = self.name.split("|")

		if self.active:
			frappe.throw(_("Cannot delete an active sieve script. Please deactivate it first."))

		SieveScript._delete_sieve_scripts(user, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		id = filters.get("id")
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view the Sieve Scripts."), alert=True)
			return []

		scripts = []
		if id:
			scripts = SieveScript._get_sieve_scripts(user, [id])
			total = len(scripts)
		else:
			filter = {}
			if value := filters.get("_name"):
				filter["name"] = value
			if value := filters.get("active"):
				filter["isActive"] = bool(cint(value))

			limit = cint(kwargs.get("start")) + page_length
			scripts, total = SieveScript._fetch_sieve_scripts(user, filter, limit=limit)

		frappe.cache.set_value(_get_total_cache_key(user), total, expires_in_sec=600)

		if not scripts:
			frappe.msgprint(_("No sieve scripts found."), alert=True)

		return scripts

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

	@classmethod
	def _add_sieve_script(
		cls,
		user: str,
		name: str,
		content: str,
		active: bool = False,
	) -> str:
		"""Adds a sieve script for the given user with the specified parameters."""

		has_permission_for_user(user)

		creation_id = str(uuid7())
		client = get_jmap_client(user)
		blob = client.upload_blob(content.encode("utf-8"), "application/sieve")
		response = client.sieve_script_create(creation_id, name, blob["blobId"], active)

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
		user: str,
		filter: dict | None = None,
		position: int = 0,
		limit: int = 50,
	) -> list:
		"""Returns a list of sieve scripts for the given user."""

		has_permission_for_user(user)

		scripts = []
		client = get_jmap_client(user)

		while len(scripts) < limit:
			result = client.sieve_script_query(filter, position, limit)
			ids = result["ids"]
			total = result["total"]

			if not ids:
				break

			scripts.extend(SieveScript._get_sieve_scripts(user, ids))

			if len(scripts) >= limit:
				break

			position += len(ids)

			if position >= total:
				break

		return scripts[:limit], total

	@classmethod
	def _get_sieve_scripts(cls, user: str, ids: list[str]) -> list[dict]:
		"""Returns a list of sieve scripts for the provided IDs in the same order as ids."""

		has_permission_for_user(user)

		sieve_scripts = {}

		client = get_jmap_client(user)
		scripts = client.sieve_script_get(ids)

		if frappe.flags.download_sieve_script_content:
			blobs = [(s["blobId"], None) for s in scripts if s["blobId"]]
			data = client.download_blobs_concurrently(blobs)

			for script in scripts:
				script["content"] = data.get(script["blobId"], b"").decode("utf-8")

		for script in scripts:
			script = format_sieve_script(user, script)
			sieve_scripts[script["id"]] = script

		return [sieve_scripts[id] for id in ids if id in sieve_scripts]

	@classmethod
	def _validate_sieve_script(cls, user: str, content: str) -> None:
		"""Validates a sieve script for the given user."""

		if not content.strip():
			frappe.throw(_("Sieve script content cannot be empty."))

		has_permission_for_user(user)

		client = get_jmap_client(user)
		blob = client.upload_blob(content.encode("utf-8"), "application/sieve")
		response = client.sieve_script_validate(blob["blobId"])

		if error := response.get("error"):
			frappe.throw(
				_("{0}: {1}").format(error.get("type"), error.get("description")),
				title=_("Sieve Script Validation Error"),
			)

	@classmethod
	def _update_sieve_script(
		cls,
		user: str,
		id: str,
		name: str,
		content: str,
		active: bool = False,
	) -> None:
		"""Updates a sieve script for the given user and ID with the specified parameters."""

		if not content.strip():
			frappe.throw(_("Sieve script content cannot be empty."))

		has_permission_for_user(user)

		client = get_jmap_client(user)
		scripts = client.sieve_script_get([id])

		if not scripts:
			frappe.throw(
				_("Sieve Script with ID {0} not found.").format(frappe.bold(id)),
				title=_("Sieve Script Not Found"),
			)

		script = scripts[0]
		blob_id = script["blobId"]
		current_content = client.download_blob(blob_id).decode("utf-8")

		if content != current_content:
			new_blob = client.upload_blob(content.encode("utf-8"), "application/sieve")
			blob_id = new_blob["blobId"]

		deactivate = script["isActive"] and not active
		response = client.sieve_script_update(id, name, blob_id, active, deactivate)

		title = _("Sieve Script Update Error")
		if not response.get("updated"):
			if response.get("notUpdated"):
				frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
			else:
				frappe.throw(_(response["description"]), title=title)

	@classmethod
	def _delete_sieve_scripts(cls, user: str, ids: list[str]) -> None:
		"""Deletes sieve scripts for the given list of IDs and user."""

		has_permission_for_user(user)

		client = get_jmap_client(user)
		response = client.sieve_script_delete(ids)

		if response.get("notDestroyed"):
			error_messages = []
			for id, error in response["notDestroyed"].items():
				error_messages.append(f"{id}: {error['description']}")
			frappe.throw(
				_("Sieve Script Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
				title=_("Sieve Script Deletion Error"),
			)

	@frappe.whitelist()
	def validate_script(self) -> None:
		"""Validates the sieve script content."""

		user, _id = self.name.split("|")

		has_permission_for_user(user)

		self._validate_sieve_script(user, self.content)
		frappe.msgprint(_("Sieve script is valid."), indicator="green", alert=True)


def _get_total_cache_key(user: str) -> str:
	"""Returns a cache key for total sieve scripts count for the given user."""

	return f"{user}:sieve_scripts:total"


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes multiple sieve scripts given their names."""

	if isinstance(names, str):
		names = json.loads(names)

	user_ids_map = {}
	for name in names:
		user, id = name.split("|")
		user_ids_map.setdefault(user, []).append(id)

	for user, ids in user_ids_map.items():
		SieveScript._delete_sieve_scripts(user, ids)

	frappe.msgprint(_("Sieve Scripts deleted successfully."), alert=True)


def format_sieve_script(user: str, script: dict) -> dict:
	"""Format the sieve script for display.z"""

	return {
		"name": f"{user}|{script['id']}",
		"user": user,
		"id": script["id"],
		"_name": script["name"],
		"active": cint(script["isActive"]),
		"blob_id": script["blobId"],
		"content": script.get("content") or "",
		"creation": today(),
		"modified": today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Sieve Script":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
