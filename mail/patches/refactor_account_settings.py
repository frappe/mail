import frappe


def execute() -> None:
	"""Reshape Account Settings into a per-account-ID, shared document.

	Previously each document was per user, named by a UUID, with `user` and `account`
	(`user:account_id`) columns. The document is now named by the bare JMAP account ID
	and shared across every user with access. This runs pre_model_sync (while the old
	columns still exist) to rename/dedupe documents to their account ID. The first
	document per account ID wins; the rest are dropped.

	The legacy Outgoing settings are copied over by migrate_outgoing_settings_to_account
	in post_model_sync — they can't be written here because those columns only land on
	Account Settings during model sync.
	"""

	if not frappe.db.has_column("Account Settings", "account"):
		# Fresh install (or already migrated) — nothing to reshape.
		return

	seen: set[str] = set()
	rows = frappe.db.get_all(
		"Account Settings",
		fields=["name", "account"],
		order_by="creation asc",
	)

	for row in rows:
		account = (row.get("account") or "").strip()
		account_id = account.split(":", 1)[1].strip() if ":" in account else ""

		if account_id and row["name"] == account_id:
			# Already renamed by an earlier (interrupted) run of this patch.
			seen.add(account_id)
			continue

		if not account_id or account_id in seen or frappe.db.exists("Account Settings", account_id):
			frappe.delete_doc(
				"Account Settings", row["name"], force=True, ignore_permissions=True, delete_permanently=True
			)
			continue

		seen.add(account_id)
		frappe.rename_doc(
			"Account Settings",
			row["name"],
			account_id,
			force=True,
			show_alert=False,
		)
