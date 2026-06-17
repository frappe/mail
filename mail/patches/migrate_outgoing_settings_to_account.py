import frappe

from mail.client.doctype.account_settings.account_settings import backfill_default_outgoing_emails
from mail.patches.capture_user_outgoing_settings import CACHE_KEY


def execute() -> None:
	"""Apply the captured per-user Outgoing settings onto each Account Settings.

	The three toggles and the old default_outgoing_email are copied verbatim to every
	account the user owns (JMAP isn't reliably reachable during `bench migrate`, so we
	can't resolve identities here). The per-account default is then finalised against
	each account's identities by a background job once migrate is done.
	"""

	captured = frappe.cache.get_value(CACHE_KEY)
	by_user = frappe.parse_json(captured) if captured else {}

	for settings in frappe.get_all("Account Settings", fields=["name", "account", "user"]):
		old = by_user.get(settings["user"])
		if not old:
			continue

		frappe.db.set_value(
			"Account Settings",
			settings["name"],
			{
				"default_outgoing_email": old.get("default_outgoing_email"),
				"create_contacts_after_email_submit": old.get("create_contacts_after_email_submit") or 0,
				"destroy_email_after_submit": old.get("destroy_email_after_submit") or 0,
				"destroy_newsletter_after_submit": old.get("destroy_newsletter_after_submit") or 0,
			},
			update_modified=False,
		)

	if captured:
		frappe.cache.delete_value(CACHE_KEY)

	# Resolve each account's default outgoing email against its identities once migrate
	# is done — JMAP returns nothing while the migrate process is running.
	frappe.enqueue(backfill_default_outgoing_emails, queue="long", enqueue_after_commit=True)
