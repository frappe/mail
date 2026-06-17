import frappe

CACHE_KEY = "migrate:user_outgoing_settings"


def execute() -> None:
	"""Capture the per-user Outgoing settings before they are dropped from User Settings.

	The fields move to Account Settings (per-account). This patch runs pre_model_sync
	(the User Settings columns still exist); the values are stashed in cache and applied
	to Account Settings by migrate_outgoing_settings_to_account in post_model_sync (once
	the new columns exist). The fields are already gone from the doctype meta but the
	columns still exist in the table, so the query builder references them by column name.
	"""

	if not frappe.db.has_column("User Settings", "default_outgoing_email"):
		return

	US = frappe.qb.DocType("User Settings")
	rows = (
		frappe.qb.from_(US).select(
			US.user,
			US.default_outgoing_email,
			US.create_contacts_after_email_submit,
			US.destroy_email_after_submit,
			US.destroy_newsletter_after_submit,
		)
	).run(as_dict=True)

	frappe.cache.set_value(CACHE_KEY, frappe.as_json({r["user"]: r for r in rows}))
