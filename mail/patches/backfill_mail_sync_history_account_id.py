import frappe

from mail.jmap import parse_account


def execute() -> None:
	"""Backfill `Mail Sync History.account_id` from the per-user "user:account_id" handle so the
	sync watermark is keyed on the shared account_id rather than per user.

	The (account_id, source) unique index is added during model sync, when existing rows still have
	a NULL account_id (NULLs are distinct, so the index applies cleanly). This patch then
	deduplicates (account_id, source) and fills account_id in, and drops the now-redundant per-handle
	index.
	"""

	if not frappe.db.has_column("Mail Sync History", "account"):
		# The per-user `account` handle was later dropped (watermark shared per account_id);
		# nothing to backfill on fresh installs.
		return

	rows = frappe.get_all(
		"Mail Sync History",
		fields=["name", "account", "source", "last_received_at"],
		order_by="last_received_at desc",
	)

	seen: set[tuple[str, str]] = set()
	duplicates: list[str] = []
	updates: list[tuple[str, str]] = []

	for row in rows:
		try:
			account_id = parse_account(row.account)[1]
		except Exception:
			continue  # skip malformed handles rather than abort the migration

		key = (account_id, row.source)
		if key in seen:
			duplicates.append(row.name)
		else:
			seen.add(key)
			updates.append((row.name, account_id))

	# Drop redundant duplicate rows first (same source synced by multiple users on a shared account)
	# so populating account_id can't violate the unique (account_id, source) index. Rows are ordered
	# by most-recent last_received_at, so the freshest watermark per (account_id, source) is kept.
	if duplicates:
		frappe.db.delete("Mail Sync History", {"name": ["in", duplicates]})

	for name, account_id in updates:
		frappe.db.set_value("Mail Sync History", name, "account_id", account_id, update_modified=False)

	# The watermark is keyed on account_id now; drop the stale per-handle unique index.
	if frappe.db.has_index("tabMail Sync History", "unique_account_source"):
		frappe.db.sql_ddl("ALTER TABLE `tabMail Sync History` DROP INDEX `unique_account_source`")
