import frappe
from frappe import _

from mail.backend import MailBackendAccountManager
from mail.utils.cache import get_cluster_for_tenant
from mail.utils.user import get_user_hashed_password


def execute() -> None:
	domains = frappe.db.get_all("Mail Domain", {"enabled": 1, "is_verified": 1}, pluck="name")
	accounts = frappe.db.get_all("Mail Account", pluck="name")

	for account in accounts:
		try:
			doc = frappe.get_doc("Mail Account", account)
			secret_hash = get_user_hashed_password(doc.user)
			doc._db_set(secret_hash=secret_hash)

			if not doc.enabled or doc.domain_name not in domains:
				continue

			if hasattr(doc, "password") and doc.password:
				account_password = doc.get_password("password")
				doc._generate_app_password(account_password)

			MailBackendAccountManager("Mail Cluster", get_cluster_for_tenant(doc.tenant)).update(
				doc.email, doc.display_name, secret_hash, old_secret=""
			)
		except Exception:
			frappe.log_error(
				_("Failed to set password for account {0}").format(account),
				frappe.get_traceback(with_context=True),
			)
