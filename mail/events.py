import json

import frappe
from frappe import _
from frappe.model.document import Document

from mail.backend import get_mail_backend_api
from mail.jmap import JMAPClient
from mail.server.doctype.mail_principal.mail_principal import PRINCIPAL_ENDPOINT, _get_principal
from mail.utils import reformat_pbkdf2_hash
from mail.utils.user import (
	get_cluster_for_tenant,
	get_tenant_for_user,
	get_user_hashed_password,
	is_tenant_bound_user,
)
from mail.utils.validation import ensure_tenant_has_cluster


def validate_jmap_settings(doc: Document, method: str | None = None) -> None:
	"""Validate JMAP settings on User document."""

	if not doc.enabled:
		return

	if doc.jmap_server_url or doc.jmap_username or doc.jmap_app_password:
		if not doc.jmap_server_url:
			frappe.throw(_("JMAP Server URL is required if JMAP settings are provided."))

		if not doc.jmap_username:
			frappe.throw(_("JMAP Username is required if JMAP settings are provided."))

		if not doc.jmap_app_password:
			frappe.throw(_("JMAP App Password is required if JMAP settings are provided."))

	if doc.jmap_default_outgoing_email:
		client = JMAPClient(doc.jmap_server_url, doc.jmap_username, doc.get_password("jmap_app_password"))
		identities = client.identity_get()
		if not any(identity.get("email") == doc.jmap_default_outgoing_email for identity in identities):
			frappe.throw(
				_("Default Outgoing Email {0} is not found in the identities of the JMAP account.").format(
					frappe.bold(doc.jmap_default_outgoing_email)
				)
			)

	if not is_tenant_bound_user(doc.name):
		return

	if doc.jmap_username:
		if doc.jmap_username != doc.name:
			frappe.throw(_("JMAP Username must be the same as the User name."))

		tenant = get_tenant_for_user(doc.name)
		if not frappe.db.exists(
			"Mail Principal Binding",
			{"tenant": tenant, "principal_name": doc.jmap_username},
			"principal_name",
		):
			frappe.throw(
				_("Account {0} is not bound to Tenant {1}").format(
					frappe.bold(doc.jmap_username), frappe.bold(tenant)
				)
			)


def update_account_password(doc: Document, method: str | None = None) -> None:
	"""Update the password in the Mail Principal when the User's password is changed."""

	if not doc.enabled:
		return

	if not is_tenant_bound_user(doc.name):
		return

	tenant = get_tenant_for_user(doc.name)
	ensure_tenant_has_cluster(tenant)
	backend = get_mail_backend_api("Mail Cluster", get_cluster_for_tenant(tenant))
	principal = _get_principal(backend, doc.jmap_username, ignore_not_found=False)

	actions = []
	for secret in principal.get("secrets", []):
		if not secret.startswith("$app$"):
			actions.append({"action": "removeItem", "field": "secrets", "value": secret})

	if hashed_password := get_user_hashed_password(doc.name):
		actions.append(
			{"action": "addItem", "field": "secrets", "value": reformat_pbkdf2_hash(hashed_password)}
		)

	if actions:
		response = backend.request(
			"PATCH", f"{PRINCIPAL_ENDPOINT}/{doc.jmap_username}", data=json.dumps(actions)
		)

		if response.status_code != 200 or response.json().get("error"):
			frappe.throw(
				_("Failed to update password for Mail Principal {0}. Response: {1}").format(
					frappe.bold(doc.jmap_username), frappe.bold(response.text)
				)
			)
