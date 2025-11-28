# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today
from uuid_utils import uuid7

from mail.jmap import get_jmap_client
from mail.server.doctype.mail_backend_request.mail_backend_request import create_mail_backend_request
from mail.utils import parse_filters
from mail.utils.cache import get_account_for_user, get_cluster_for_tenant
from mail.utils.user import has_role, is_administrator, is_tenant_admin
from mail.utils.validation import has_permission_for_account


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
		delete_identity(account, id)

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		account = filters.get("account") or get_account_for_user(frappe.session.user)

		if not account:
			frappe.msgprint(_("Please select a account to view identities."), alert=True)
			return []

		identities = fetch_identities(account, limit=page_length)

		if not identities:
			frappe.msgprint(_("No identities found."), alert=True)

		return identities

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		account = filters.get("account") or get_account_for_user(frappe.session.user)
		return frappe.cache.get_value(get_total_cache_key(account)) if account else 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}


def get_total_cache_key(account: str) -> str:
	"""Returns a cache key for total identities count for the given account."""

	return f"{account}:identities:total"


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

	user = frappe.session.user
	tenant = frappe.db.get_value("Mail Account", account, "tenant")
	if not (is_administrator(user) or is_tenant_admin(tenant, user)):
		frappe.throw(
			_("User {0} does not have permission to create identity for account {1}.").format(
				frappe.bold(user), frappe.bold(account)
			)
		)

	creation_id = str(uuid7())
	payload = {
		"using": ["urn:ietf:params:jmap:mail"],
		"methodCalls": [
			[
				"Identity/set",
				{
					"accountId": get_jmap_client(account).primary_account_id,
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
def get_identity(account: str, id: str) -> dict:
	"""Returns identity details for the given name in the format 'account|id'."""

	has_permission_for_account(account)

	client = get_jmap_client(account)
	if identities := client.identity_get([id]):
		return format_identity(account, identities[0])

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

	has_permission_for_account(account)

	client = get_jmap_client(account)
	response = client.identity_update(id, name, reply_to, bcc, text_signature, html_signature)

	if not response.get("updated"):
		title = _("Identity Update Error")
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_identity(account: str, id: str) -> None:
	"""Deletes a identity for the given account by its ID."""

	has_permission_for_account(account)

	client = get_jmap_client(account)
	response = client.identity_delete([id])

	if response.get("notDestroyed"):
		frappe.throw(_(response["notDestroyed"][id]["description"]), title=_("Identity Deletion Error"))


@frappe.whitelist()
def fetch_identities(account: str, page: int = 1, limit: int = 10) -> list:
	"""Returns a list of identities for the given account."""

	has_permission_for_account(account)

	client = get_jmap_client(account)
	identities = client.identity_get()
	formatted_identities = [format_identity(account, identity) for identity in identities]
	frappe.cache.set_value(get_total_cache_key(account), len(identities), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_identities[start:end]


def format_identity(account: str, identity: dict) -> dict:
	"""Formats identity data for display."""

	bcc = []
	for b in identity["bcc"] or []:
		bcc.append({"display_name": b["name"], "email": b["email"]})

	reply_to = []
	for r in identity["replyTo"] or []:
		reply_to.append({"display_name": r["name"], "email": r["email"]})

	return {
		"name": f"{account}|{identity['id']}",
		"account": account,
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

	user = user or frappe.session.user

	if is_administrator(user):
		return True

	if has_role(user, "Mail User"):
		return doc.account == get_account_for_user(user)

	return False
