import frappe

from mail.client.doctype.user_settings.user_settings import (
	create_frappe_mail_automation_script,
)


def execute() -> None:
	"""Create frappe_mail_automation sieve script for every mail user."""

	for user in frappe.get_all("User Settings", {"username": ["!=", None]}, pluck="user"):
		create_frappe_mail_automation_script(user)
