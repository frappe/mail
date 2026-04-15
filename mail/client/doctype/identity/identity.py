# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from mail.backend import get_mail_backend_api
from mail.jmap import get_identity_service, parse_account
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
			self.account,
			self.email,
			self._name,
			self._reply_to,
			self._bcc,
			self.text_signature,
			self.html_signature,
		)
		self.name = f"{self.account}|{self.id}"

	def load_from_db(self) -> "Identity":
		account, id = self.name.split("|")
		identity = get_identity(account, id)
		return super(Document, self).__init__(identity)

	def db_update(self) -> None:
		update_identity(
			self.account,
			self.id,
			self._name,
			self._reply_to,
			self._bcc,
			self.text_signature,
			self.html_signature,
		)
		self.reload()

	def delete(self) -> None:
		account, id = self.name.split("|")
		delete_identities(account, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		id = filters.get("id")
		account = filters.get("account")

		if not account:
			frappe.msgprint(_("Please select an account to view identities."), alert=True)
			return []

		identities = []
		if id:
			if identity := get_identity(account, id, raise_exception=False):
				identities.append(identity)
		else:
			identities = fetch_identities(account, limit=page_length)

		if not identities:
			frappe.msgprint(_("No identities found."), alert=True)

		return identities

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
	"""Returns a cache key for total identities count for the given account."""

	return f"{account}:identities:total"


def _add_identity(
	account: str,
	email: str,
	name: str | None = None,
	reply_to: list[dict] | None = None,
	bcc: list[dict] | None = None,
	text_signature: str | None = None,
	html_signature: str | None = None,
) -> str:
	"""Adds an identity for the given account with the specified parameters."""

	user, account_id = parse_account(account)

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
					"accountId": account_id,
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

	account_ids_map = {}
	for name in names:
		account, id = name.split("|")
		account_ids_map.setdefault(account, []).append(id)

	for account, ids in account_ids_map.items():
		delete_identities(account, ids)

	frappe.msgprint(_("Identities deleted successfully."), alert=True)


@frappe.whitelist()
def add_identity(
	account: str,
	email: str,
	name: str | None = None,
	reply_to: list[dict] | None = None,
	bcc: list[dict] | None = None,
	text_signature: str | None = None,
	html_signature: str | None = None,
) -> str:
	"""Adds an identity for the given account with the specified parameters."""

	user, _account_id = parse_account(account)
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

	service = get_identity_service(account)
	response = service.create([identity])

	title = _("Identity Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_identity(account: str, id: str, raise_exception: bool = True) -> dict | None:
	"""Returns identity details for the given name in the format 'account|id'."""

	user, _account_id = parse_account(account)
	has_permission_for_identity(user)

	service = get_identity_service(account)
	if identities := service.get([id]):
		return format_identity(account, identities[0])

	if raise_exception:
		frappe.throw(
			_("Identity with ID {0} not found in account {1}.").format(frappe.bold(id), frappe.bold(account)),
			title=_("Identity Not Found"),
		)


@frappe.whitelist()
def update_identity(
	account: str,
	id: str,
	name: str | None = None,
	reply_to: list[dict] | None = None,
	bcc: list[dict] | None = None,
	text_signature: str | None = None,
	html_signature: str | None = None,
) -> None:
	"""Updates an existing identity with the given parameters."""

	user, _account_id = parse_account(account)
	has_permission_for_user(user)

	identity = {
		"id": id,
		"name": name,
		"reply_to": reply_to,
		"bcc": bcc,
		"text_signature": text_signature,
		"html_signature": html_signature,
	}

	service = get_identity_service(account)
	response = service.update([identity])

	if not response.get("updated"):
		title = _("Identity Update Error")
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_identities(account: str, ids: list[str]) -> None:
	"""Deletes identities for the given account and list of identity IDs."""

	user, _account_id = parse_account(account)
	has_permission_for_identity(user)

	service = get_identity_service(account, ignore_permissions=True)
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
def fetch_identities(account: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of identities for the given account."""

	user, _account_id = parse_account(account)

	if not has_permission_for_user(user, raise_exception=False):
		if not is_mail_admin(frappe.session.user):
			frappe.throw(
				_("User {0} does not have permission to view identities for user {1}.").format(
					frappe.bold(frappe.session.user), frappe.bold(user)
				)
			)

	service = get_identity_service(account, ignore_permissions=True)
	identities = service.get()

	formatted_identities = [format_identity(account, identity) for identity in identities]
	frappe.cache.set_value(_get_total_cache_key(account), len(identities), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_identities[start:end]


def format_identity(account: str, identity: dict) -> dict:
	"""Formats identity data for display."""

	bcc = []
	for b in identity["bcc"] or []:
		bcc.append({"display_name": b["name"], "email": b["email"].lower()})

	reply_to = []
	for r in identity["replyTo"] or []:
		reply_to.append({"display_name": r["name"], "email": r["email"].lower()})

	return {
		"name": f"{account}|{identity['id']}",
		"account": account,
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

	doc_user, _account_id = parse_account(doc.account)

	return has_permission_for_user(doc_user, raise_exception=False)
