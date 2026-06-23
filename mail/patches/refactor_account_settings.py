import frappe

from mail.patches.capture_user_outgoing_settings import CACHE_KEY


def execute() -> None:
	"""Reshape Account Settings into a per-account-ID, shared document.

	Previously each document was per user, named by a UUID, with `user` and `account`
	(`user:account_id`) columns. The document is now named by the bare JMAP account ID
	and shared across every user with access. This runs pre_model_sync (while the old
	columns still exist) to rename/dedupe documents to their account ID. The first
	document per account ID wins; the rest are dropped.
	"""

	if not frappe.db.has_column("Account Settings", "account"):
		# Fresh install (or already migrated) — nothing to reshape.
		return

	captured = frappe.cache.get_value(CACHE_KEY)
	by_user = frappe.parse_json(captured) if captured else {}

	seen: set[str] = set()
	rows = frappe.db.get_all(
		"Account Settings",
		fields=["name", "account", "user"],
		order_by="creation asc",
	)

	for row in rows:
		account = (row.get("account") or "").strip()
		account_id = account.split(":", 1)[1].strip() if ":" in account else ""

		if not account_id or account_id in seen or frappe.db.exists("Account Settings", account_id):
			frappe.delete_doc(
				"Account Settings", row["name"], force=True, ignore_permissions=True, delete_permanently=True
			)
			continue

		# Apply any per-user Outgoing settings captured before they were dropped from
		# User Settings (no-op on sites that already ran migrate_outgoing_settings_to_account).
		if old := by_user.get(row.get("user")):
			frappe.db.set_value(
				"Account Settings",
				row["name"],
				{
					"default_outgoing_email": old.get("default_outgoing_email"),
					"create_contacts_after_email_submit": old.get("create_contacts_after_email_submit") or 0,
					"destroy_email_after_submit": old.get("destroy_email_after_submit") or 0,
					"destroy_newsletter_after_submit": old.get("destroy_newsletter_after_submit") or 0,
				},
				update_modified=False,
			)

		seen.add(account_id)
		frappe.rename_doc(
			"Account Settings",
			row["name"],
			account_id,
			force=True,
			ignore_permissions=True,
			show_alert=False,
		)

	if captured:
		frappe.cache.delete_value(CACHE_KEY)
