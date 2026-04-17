import time

import frappe

from mail.client.doctype.sieve_script.sieve_script import SieveScript


def execute() -> None:
	"""Create frappe_mail_automation sieve script for every mail user."""

	for user in frappe.get_all("User Settings", {"username": ["!=", None]}, pluck="user"):
		try:
			existing_scripts = SieveScript._fetch_sieve_scripts(
				user, filter={"name": "frappe_mail_automation"}
			)[0]

			if existing_scripts:
				continue

			SieveScript._add_sieve_script(
				user=user,
				name="frappe_mail_automation",
				content='require ["fileinto", "imap4flags"];',
				active=False,
			)

		except Exception as e:
			frappe.log_error(
				title="Sieve Script Creation Failed",
				message=f"Failed to create frappe_mail_automation script for user {user}: {e!s}",
			)
