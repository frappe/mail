import frappe

from mail.api.sieve import backfill_mailbox_automation_rules


def execute() -> None:
	"""Capture existing folder automation rules into the Mailbox Settings backup.

	Folder rules used to live only inside the frappe_mail_automation sieve script. Now that Mailbox
	Settings is the source of truth the script is generated from, copy the existing rules over so the
	first rebuild doesn't drop them. JMAP isn't reachable during `bench migrate`, so it runs as a
	background job once migrate is done (same approach as the outgoing-settings backfill).
	"""

	frappe.enqueue(backfill_mailbox_automation_rules, queue="long", enqueue_after_commit=True)
