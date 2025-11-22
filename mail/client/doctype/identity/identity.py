# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today
from uuid_utils import uuid7

from mail.jmap import get_jmap_client_for_user
from mail.server.doctype.mail_backend_request.mail_backend_request import create_mail_backend_request
from mail.utils import parse_filters
from mail.utils.cache import get_cluster_for_tenant
from mail.utils.user import is_administrator, is_tenant_admin
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
		delete_identity(user, id)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view identities."), alert=True)
			return []

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


@frappe.whitelist()
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

	user = frappe.session.user
	tenant = frappe.db.get_value("Mail Account", user, "tenant")
	if not (is_administrator(user) or is_tenant_admin(tenant, user)):
		frappe.throw(
			_("User {0} does not have permission to create identity for user {1}.").format(
				frappe.bold(user), frappe.bold(user)
			)
		)

	creation_id = str(uuid7())
	payload = {
		"using": ["urn:ietf:params:jmap:mail"],
		"methodCalls": [
			[
				"Identity/set",
				{
					"accountId": get_jmap_client_for_user(user).primary_account_id,
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

	request = create_mail_backend_request(
		"Mail Cluster",
		get_cluster_for_tenant(tenant),
		method="POST",
		endpoint="/jmap",
		request_json=payload,
		do_not_enqueue=True,
	)

	title = _("Identity Creation Error")
	if request.status == "Completed":
		response = json.loads(request.response_json)["methodResponses"][0][1]
		if response.get("created"):
			return response["created"][creation_id]["id"]
		elif response.get("notCreated"):
			frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)

	frappe.throw(_("Identity creation request failed."), title=title)


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
	client = get_jmap_client_for_user(user)
	response = client.identity_create(creation_id, email, name, reply_to, bcc, text_signature, html_signature)

	title = _("Identity Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_identity(user: str, id: str) -> dict:
	"""Returns identity details for the given name in the format 'user|id'."""

	has_permission_for_user(user)

	client = get_jmap_client_for_user(user)
	if identities := client.identity_get([id]):
		return format_identity(user, identities[0])

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

	client = get_jmap_client_for_user(user)
	response = client.identity_update(id, name, reply_to, bcc, text_signature, html_signature)

	if not response.get("updated"):
		title = _("Identity Update Error")
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_identity(user: str, id: str) -> None:
	"""Deletes a identity for the given user by its ID."""

	has_permission_for_user(user)

	client = get_jmap_client_for_user(user)
	response = client.identity_delete([id])

	if response.get("notDestroyed"):
		frappe.throw(_(response["notDestroyed"][id]["description"]), title=_("Identity Deletion Error"))


@frappe.whitelist()
def fetch_identities(user: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of identities for the given user."""

	has_permission_for_user(user)

	client = get_jmap_client_for_user(user)
	identities = client.identity_get()
	formatted_identities = [format_identity(user, identity) for identity in identities]
	frappe.cache.set_value(_get_total_cache_key(user), len(identities), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_identities[start:end]


def format_identity(user: str, identity: dict) -> dict:
	"""Formats identity data for display."""

	bcc = []
	for b in identity["bcc"] or []:
		bcc.append({"display_name": b["name"], "email": b["email"]})

	reply_to = []
	for r in identity["replyTo"] or []:
		reply_to.append({"display_name": r["name"], "email": r["email"]})

	return {
		"name": f"{user}|{identity['id']}",
		"user": user,
		"id": identity["id"],
		"_name": identity["name"],
		"email": identity["email"],
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
