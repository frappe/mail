# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from mail.backend import get_mail_backend_api
from mail.jmap import get_identity_service
from mail.utils import parse_filters
from mail.utils.user import is_administrator, is_mail_admin
from mail.utils.validation import has_permission_for_user


class Identity(Document):
	@property
	def _bcc(self) -> list[dict]:
		"""Returns the BCC list in the JMAP required format."""

		bcc = []
		for b in self.bcc:
			bcc.append({"name": b.display_name, "email": b.email})
		return bcc

	@property
	def _reply_to(self) -> list[dict]:
		"""Returns the Reply-To list in the JMAP required format."""

		reply_to = []
		for r in self.reply_to:
			reply_to.append({"name": r.display_name, "email": r.email})
		return reply_to

	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_identity(
			self.user,
			self.email,
			self._name,
			self._reply_to,
			self._bcc,
			self.text_signature,
			self.html_signature,
		)
		self.name = f"{self.user}|{self.id}"

	def load_from_db(self) -> "Identity":
		user, id = self.name.split("|")
		identity = get_identity(user, id)
		return super(Document, self).__init__(identity)

	def db_update(self) -> None:
		update_identity(
			self.user,
			self.id,
			self._name,
			self._reply_to,
			self._bcc,
			self.text_signature,
			self.html_signature,
		)
		self.reload()

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_identities(user, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		id = filters.get("id")
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view identities."), alert=True)
			return []

		identities = []
		if id:
			if identity := get_identity(user, id, raise_exception=False):
				identities.append(identity)
		else:
			identities = fetch_identities(user, limit=page_length)

		if not identities:
			frappe.msgprint(_("No identities found."), alert=True)

		return identities

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
	"""Returns a cache key for total identities count for the given user."""

	return f"{user}:identities:total"


def _add_identity(
	user: str,
	email: str,
	name: str | None = None,
	reply_to: list[dict] | None = None,
	bcc: list[dict] | None = None,
	text_signature: str | None = None,
	html_signature: str | None = None,
) -> str:
	"""Adds an identity for the given user with the specified parameters."""

	if not is_administrator(frappe.session.user) and not is_mail_admin(frappe.session.user):
		frappe.throw(
			_("User {0} does not have permission to create identity for user {1}.").format(
				frappe.bold(frappe.session.user), frappe.bold(user)
			)
		)

	creation_id = str(uuid7())
	payload = {
		"using": ["urn:ietf:params:jmap:mail"],
		"methodCalls": [
			[
				"Identity/set",
				{
					"accountId": get_identity_service(user, ignore_permissions=True).primary_account_id,
					"create": {
						creation_id: {
							"email": email,
							"name": name or "",
							"replyTo": reply_to or [],
							"bcc": bcc or [],
							"textSignature": text_signature or "",
							"htmlSignature": html_signature or "",
						}
					},
				},
				"0",
			]
		],
	}

	backend = get_mail_backend_api()
	response = backend.request("POST", "/jmap", json=payload)

	title = _("Identity Creation Error")
	response = response.json()["methodResponses"][0][1]
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)

	frappe.throw(_("Identity creation request failed."), title=title)


def has_permission_for_identity(user: str) -> bool:
	"""Checks if the user has permission for the identity."""

	if not has_permission_for_user(user, raise_exception=False) and not is_mail_admin(frappe.session.user):
		frappe.throw(
			_("User {0} does not have permission to view identities for user {1}.").format(
				frappe.bold(frappe.session.user), frappe.bold(user)
			)
		)


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes multiple identities given their names."""

	if isinstance(names, str):
		names = json.loads(names)

	user_ids_map = {}
	for name in names:
		user, id = name.split("|")
		user_ids_map.setdefault(user, []).append(id)

	for user, ids in user_ids_map.items():
		delete_identities(user, ids)

	frappe.msgprint(_("Identities deleted successfully."), alert=True)


@frappe.whitelist()
def add_identity(
	user: str,
	email: str,
	name: str | None = None,
	reply_to: list[dict] | None = None,
	bcc: list[dict] | None = None,
	text_signature: str | None = None,
	html_signature: str | None = None,
) -> str:
	"""Adds an identity for the given user with the specified parameters."""

	has_permission_for_user(user)

	creation_id = str(uuid7())
	identity = {
		"creation_id": creation_id,
		"email": email,
		"name": name,
		"reply_to": reply_to,
		"bcc": bcc,
		"text_signature": text_signature,
		"html_signature": html_signature,
	}

	service = get_identity_service(user)
	response = service.create([identity])

	title = _("Identity Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_identity(user: str, id: str, raise_exception: bool = True) -> dict | None:
	"""Returns identity details for the given name in the format 'user|id'."""

	has_permission_for_identity(user)

	service = get_identity_service(user)
	if identities := service.get([id]):
		return format_identity(user, identities[0])

	if raise_exception:
		frappe.throw(
			_("Identity with ID {0} not found in user {1}.").format(frappe.bold(id), frappe.bold(user)),
			title=_("Identity Not Found"),
		)


@frappe.whitelist()
def update_identity(
	user: str,
	id: str,
	name: str | None = None,
	reply_to: list[dict] | None = None,
	bcc: list[dict] | None = None,
	text_signature: str | None = None,
	html_signature: str | None = None,
) -> None:
	"""Updates an existing identity with the given parameters."""

	has_permission_for_user(user)

	identity = {
		"id": id,
		"name": name,
		"reply_to": reply_to,
		"bcc": bcc,
		"text_signature": text_signature,
		"html_signature": html_signature,
	}

	service = get_identity_service(user)
	response = service.update([identity])

	if not response.get("updated"):
		title = _("Identity Update Error")
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_identities(user: str, ids: list[str]) -> None:
	"""Deletes identities for the given user and list of identity IDs."""

	has_permission_for_identity(user)

	service = get_identity_service(user, ignore_permissions=True)
	response = service.delete(ids)

	if response.get("notDestroyed"):
		error_messages = []
		for id, error in response["notDestroyed"].items():
			error_messages.append(f"{id}: {error['description']}")
		frappe.throw(
			_("Identity Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
			title=_("Identity Deletion Error"),
		)


@frappe.whitelist()
def fetch_identities(user: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of identities for the given user."""

	if not has_permission_for_user(user, raise_exception=False):
		if not is_mail_admin(frappe.session.user):
			frappe.throw(
				_("User {0} does not have permission to view identities for user {1}.").format(
					frappe.bold(frappe.session.user), frappe.bold(user)
				)
			)

	service = get_identity_service(user, ignore_permissions=True)
	identities = service.get()

	formatted_identities = [format_identity(user, identity) for identity in identities]
	frappe.cache.set_value(_get_total_cache_key(user), len(identities), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_identities[start:end]


def format_identity(user: str, identity: dict) -> dict:
	"""Formats identity data for display."""

	bcc = []
	for b in identity["bcc"] or []:
		bcc.append({"display_name": b["name"], "email": b["email"].lower()})

	reply_to = []
	for r in identity["replyTo"] or []:
		reply_to.append({"display_name": r["name"], "email": r["email"].lower()})

	return {
		"name": f"{user}|{identity['id']}",
		"user": user,
		"id": identity["id"],
		"_name": identity["name"],
		"email": identity["email"].lower(),
		"bcc": bcc,
		"reply_to": reply_to,
		"html_signature": identity["htmlSignature"],
		"text_signature": identity["textSignature"],
		"may_delete": cint(identity["mayDelete"]),
		"creation": today(),
		"modified": today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Identity":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
