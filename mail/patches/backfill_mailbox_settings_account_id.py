import frappe

from mail.jmap import parse_account


def execute() -> None:
	"""Backfill `Mailbox Settings.account_id` from the per-user "user:account_id" handle so the
	mailbox settings are keyed on the shared account_id rather than per user.

	The (account_id, mailbox_id) unique index is added during model sync, when existing rows still
	have a NULL account_id (NULLs are distinct, so the index applies cleanly). This patch then
	deduplicates (account_id, mailbox_id) and fills account_id in, and drops the now-redundant
	per-handle index.
	"""

	if not frappe.db.has_column("Mailbox Settings", "account"):
		# The per-user `account` handle was later dropped (settings shared per account_id);
		# nothing to backfill on fresh installs.
		return

	rows = frappe.get_all(
		"Mailbox Settings",
		fields=["name", "account", "mailbox_id"],
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

		key = (account_id, row.mailbox_id)
		if key in seen:
			duplicates.append(row.name)
		else:
			seen.add(key)
			updates.append((row.name, account_id))

	# Drop redundant duplicate settings first (same mailbox configured by multiple users on a shared
	# account) so populating account_id can't violate the unique (account_id, mailbox_id) index. The
	# earliest row per (account_id, mailbox_id) wins.
	if duplicates:
		frappe.db.delete("Mailbox Settings", {"name": ["in", duplicates]})

	for name, account_id in updates:
		frappe.db.set_value("Mailbox Settings", name, "account_id", account_id, update_modified=False)

	# The settings are keyed on account_id now; drop the stale per-handle unique index.
	if frappe.db.has_index("tabMailbox Settings", "unique_account_mailbox"):
		frappe.db.sql_ddl("ALTER TABLE `tabMailbox Settings` DROP INDEX `unique_account_mailbox`")
