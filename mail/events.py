import json

import frappe
from frappe import _
from frappe.model.document import Document

from mail.backend import get_mail_backend_api
from mail.server.doctype.principal.principal import PRINCIPAL_ENDPOINT, Principal
from mail.utils import reformat_pbkdf2_hash
from mail.utils.user import (
	get_jmap_username,
	get_user_hashed_password,
	is_local_user,
)
from mail.utils.validation import validate_mail_config


def update_account_password(doc: Document, method: str | None = None) -> None:
	"""Update the password in the Principal when the User's password is changed, but ONLY if the hash is different from the backend stored hash."""

	if not (doc.enabled and is_local_user(doc.name)):
		return

	validate_mail_config(doc.name)

	username = get_jmap_username(doc.name)

	backend = get_mail_backend_api()
	principal = Principal._fetch(backend, username, ignore_not_found=False)

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
		f"{PRINCIPAL_ENDPOINT}/{username}",
		data=json.dumps(actions),
	)

	if response.json().get("error"):
		frappe.throw(
			_("Failed to update password for Principal {0}. Response: {1}").format(
				frappe.bold(username), frappe.bold(response.text)
			)
		)
