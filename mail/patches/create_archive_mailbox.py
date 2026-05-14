import frappe

from mail.client.doctype.account_settings.account_settings import create_archive_mailbox


def execute() -> None:
	for account in frappe.get_all("Account Settings", pluck="account"):
		create_archive_mailbox(account)
