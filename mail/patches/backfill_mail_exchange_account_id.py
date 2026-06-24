import frappe

from mail.jmap import parse_account


def execute() -> None:
	"""Backfill `Mail Exchange.account_id` from the old "user:account_id" handle.

	The `account` handle was replaced by a bare `account_id` (the `user` field still carries
	the credentials used to authenticate the import/export). Each row keeps its user, so we
	just split the stored handle to fill account_id in.
	"""

	if not frappe.db.has_column("Mail Exchange", "account"):
		# Fresh install (or already migrated) — nothing to backfill.
		return

	for row in frappe.get_all("Mail Exchange", fields=["name", "account"]):
		if not row.account:
			continue

		try:
			account_id = parse_account(row.account)[1]
		except Exception:
			continue  # skip malformed handles rather than abort the migration

		frappe.db.set_value("Mail Exchange", row.name, "account_id", account_id, update_modified=False)
