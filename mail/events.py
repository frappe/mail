import frappe
from frappe.model.document import Document

from mail.backend import MailBackendAccountManager
from mail.utils.cache import get_cluster_for_tenant
from mail.utils.user import get_account_for_user, get_user_hashed_password


def update_account_password(doc: Document, method: str | None = None) -> None:
	"""Update the account password hash when the user password is changed."""

	account = get_account_for_user(doc.name)

	if not account:
		return

	account_doc = frappe.get_doc("Mail Account", account)
	current_hashed_password = get_user_hashed_password(account_doc.user)
	if account_doc.secret_hash != current_hashed_password:
		MailBackendAccountManager("Mail Cluster", get_cluster_for_tenant(account_doc.tenant)).update(
			account_doc.email,
			account_doc.display_name,
			current_hashed_password,
			old_secret=account_doc.secret_hash,
		)
		frappe.db.set_value("Mail Account", account_doc.name, "secret_hash", current_hashed_password)
