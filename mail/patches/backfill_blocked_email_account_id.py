import frappe

from mail.jmap import parse_account


def execute() -> None:
	"""Backfill `Blocked Email Address.account_id` from the per-user "user:account_id" handle so the
	block list is keyed on the shared account_id rather than per user.

	The (account_id, email) unique index is added during model sync, when existing rows still have a
	NULL account_id (NULLs are distinct, so the index applies cleanly). This patch then deduplicates
	(account_id, email) and fills account_id in, and drops the now-redundant per-handle index.
	"""

	rows = frappe.get_all(
		"Blocked Email Address",
		fields=["name", "account", "email"],
		order_by="creation asc",
	)

	seen: set[tuple[str, str]] = set()
	duplicates: list[str] = []
	updates: list[tuple[str, str]] = []

	for row in rows:
		try:
			account_id = parse_account(row.account)[1]
		except Exception:
			continue  # skip malformed handles rather than abort the migration

		key = (account_id, row.email)
		if key in seen:
			duplicates.append(row.name)
		else:
			seen.add(key)
			updates.append((row.name, account_id))

	# Drop redundant duplicate blocks first (same address blocked by multiple users on a shared
	# account) so populating account_id can't violate the unique (account_id, email) index. The set
	# of blocked addresses per account is unchanged, so the sieve scripts don't need regenerating.
	if duplicates:
		frappe.db.delete("Blocked Email Address", {"name": ["in", duplicates]})

	for name, account_id in updates:
		frappe.db.set_value("Blocked Email Address", name, "account_id", account_id, update_modified=False)

	# The block list is keyed on account_id now; drop the stale per-handle unique index.
	if frappe.db.has_index("tabBlocked Email Address", "unique_account_blocked_email"):
		frappe.db.sql_ddl("ALTER TABLE `tabBlocked Email Address` DROP INDEX `unique_account_blocked_email`")
