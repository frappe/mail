import json

import frappe
from frappe import _

from mail.utils import reformat_pbkdf2_hash
from mail.utils.cache import get_cluster_for_tenant
from mail.utils.user import get_user_hashed_password


def execute() -> None:
	domains = frappe.db.get_all("Mail Domain", {"enabled": 1, "is_verified": 1})
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

			get_req = frappe.new_doc("Mail Backend Request")
			get_req.backend_type = "Mail Cluster"
			get_req.backend_name = get_cluster_for_tenant(doc.tenant)
			get_req.method = "GET"
			get_req.endpoint = f"/api/principal/{account}"
			frappe.flags.do_not_enqueue = True
			get_req.save()

			secrets = json.loads(get_req.response_json or "{}").get("data", {}).get("secrets", [])
			request_data = [
				{
					"action": "addItem",
					"field": "secrets",
					"value": reformat_pbkdf2_hash(secret_hash),
				}
			]
			for secret in secrets:
				if not secret.startswith("$app$"):
					request_data.append({"action": "removeItem", "field": "secrets", "value": secret})

			patch_req = frappe.new_doc("Mail Backend Request")
			patch_req.backend_type = "Mail Cluster"
			patch_req.backend_name = get_cluster_for_tenant(doc.tenant)
			patch_req.method = "PATCH"
			patch_req.endpoint = f"/api/principal/{account}"
			patch_req.request_data = json.dumps(request_data)
			frappe.flags.do_not_enqueue = True
			patch_req.save()

		except Exception:
			frappe.log_error(
				_("Failed to set password for account {0}").format(account),
				frappe.get_traceback(with_context=True),
			)
