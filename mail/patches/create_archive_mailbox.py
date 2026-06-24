import frappe

from mail.client.doctype.account_settings.account_settings import create_archive_mailbox


def execute() -> None:
	# Account Settings was later reshaped to be shared per account ID, dropping the
	# `account` (`user:account_id`) column. Without it we can't build the per-user JMAP
	# connection this patch needs, so it only runs against the legacy schema; the archive
	# mailbox is created on demand by Account Settings.after_insert thereafter.
	if not frappe.db.has_column("Account Settings", "account"):
		return

	for account in frappe.get_all("Account Settings", pluck="account"):
		create_archive_mailbox(account)
