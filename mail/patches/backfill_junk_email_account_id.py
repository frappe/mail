import frappe

from mail.jmap import parse_account


def execute() -> None:
	"""Backfill `Junk Email Address.account_id` from the per-user "user:account_id" handle so the
	junk list is keyed on the shared account_id rather than per user.

	The (account_id, email) unique index is added during model sync, when existing rows still have a
	NULL account_id (NULLs are distinct, so the index applies cleanly). This patch then deduplicates
	(account_id, email) and fills account_id in, and drops the now-redundant per-handle index.
	"""

	if not frappe.db.has_column("Junk Email Address", "account"):
		# Fresh install (or already migrated) — nothing to backfill.
		return

	rows = frappe.get_all(
		"Junk Email Address",
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

	# Drop redundant duplicate junk rules first (same address junked by multiple users on a shared
	# account) so populating account_id can't violate the unique (account_id, email) index. The set
	# of junked addresses per account is unchanged, so the sieve scripts don't need regenerating.
	if duplicates:
		frappe.db.delete("Junk Email Address", {"name": ["in", duplicates]})

	for name, account_id in updates:
		frappe.db.set_value("Junk Email Address", name, "account_id", account_id, update_modified=False)

	# The junk list is keyed on account_id now; drop the stale per-handle unique index.
	if frappe.db.has_index("tabJunk Email Address", "unique_account_junk_email"):
		frappe.db.sql_ddl("ALTER TABLE `tabJunk Email Address` DROP INDEX `unique_account_junk_email`")
