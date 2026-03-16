import json

import frappe
from frappe import _
from frappe.model.document import Document

from mail.backend import get_mail_backend_api
from mail.jmap.connection import JMAPConnection, JMAPConnectionInfo
from mail.jmap.services.mail.identity import IdentityService
from mail.server.doctype.mail_principal.mail_principal import PRINCIPAL_ENDPOINT, MailPrincipal
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

	_require_fields_if_any_present(doc, ["jmap_server_url", "jmap_username", "jmap_app_password"])
	_validate_default_outgoing_email(doc)

	if not is_tenant_bound_user(doc.name):
		return

	_validate_tenant_bound_user(doc)


def update_account_password(doc: Document, method: str | None = None) -> None:
	"""Update the password in the Principal when the User's password is changed, but ONLY if the hash is different from the backend stored hash."""

	if not (doc.enabled and is_tenant_bound_user(doc.name) and doc.jmap_username):
		return

	tenant = get_tenant_for_user(doc.name)
	ensure_tenant_has_cluster(tenant)

	backend = get_mail_backend_api("Mail Cluster", get_cluster_for_tenant(tenant))
	principal = MailPrincipal._fetch(backend, doc.jmap_username, ignore_not_found=False)

	backend_secrets = principal.get("secrets", [])
	backend_hash = next((s for s in backend_secrets if not s.startswith("$app$")), None)

	user_hash = get_user_hashed_password(doc.name)
	reformatted_user_hash = reformat_pbkdf2_hash(user_hash) if user_hash else None

	if not reformatted_user_hash or reformatted_user_hash == backend_hash:
		return

	# Remove all non-app secrets
	actions = [
		{"action": "removeItem", "field": "secrets", "value": secret}
		for secret in backend_secrets
		if not secret.startswith("$app$")
	]

	# Add new password hash
	actions.append(
		{
			"action": "addItem",
			"field": "secrets",
			"value": reformatted_user_hash,
		}
	)

	response = backend.request(
		"PATCH",
		f"{PRINCIPAL_ENDPOINT}/{doc.jmap_username}",
		data=json.dumps(actions),
	)

	if response.json().get("error"):
		frappe.throw(
			_("Failed to update password for Mail Principal {0}. Response: {1}").format(
				frappe.bold(doc.jmap_username), frappe.bold(response.text)
			)
		)


def _require_fields_if_any_present(doc: Document, fields: list[str]) -> None:
	"""If any field is provided, ensure all fields are provided."""

	if any(getattr(doc, f) for f in fields):
		for f in fields:
			if not getattr(doc, f):
				frappe.throw(
					_("{0} is required if JMAP settings are provided.").format(f.replace("_", " ").title())
				)


def _validate_default_outgoing_email(doc: Document) -> None:
	"""Ensure default outgoing email exists in JMAP identities."""

	if not doc.jmap_default_outgoing_email:
		return

	info = JMAPConnectionInfo(doc.jmap_server_url, doc.jmap_username, doc.get_password("jmap_app_password"))
	connection = JMAPConnection(info)
	identity_service = IdentityService(doc.name, connection)

	if not identity_service.get_identity_id_by_email(doc.jmap_default_outgoing_email):
		frappe.throw(
			_("Default Outgoing Email {0} is not found in the identities of the JMAP account.").format(
				frappe.bold(doc.jmap_default_outgoing_email)
			)
		)


def _validate_tenant_bound_user(doc: Document) -> None:
	"""Validates JMAP settings for a tenant-bound user."""

	if not doc.jmap_username:
		return

	if doc.jmap_username != doc.name:
		frappe.throw(_("JMAP Username must be the same as the User name."))

	tenant = get_tenant_for_user(doc.name)

	exists = frappe.db.exists(
		"Mail Principal Binding",
		{"tenant": tenant, "principal_name": doc.jmap_username},
		"principal_name",
	)

	if not exists:
		frappe.throw(
			_("Account {0} is not bound to Tenant {1}").format(
				frappe.bold(doc.jmap_username), frappe.bold(tenant)
			)
		)
