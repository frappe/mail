import frappe

from mail.client.doctype.account_settings.account_settings import backfill_default_outgoing_emails

OUTGOING_FIELDS = (
	"default_outgoing_email",
	"create_contacts_after_email_submit",
	"destroy_email_after_submit",
	"destroy_newsletter_after_submit",
)


def execute() -> None:
	"""Copy the legacy per-user Outgoing settings onto each Account Settings.

	The fields moved from User Settings (per user) to Account Settings (per account ID).
	This has to run post_model_sync — the columns only land on Account Settings during
	model sync. Schema sync never drops columns, so the legacy ones are still readable
	here (User Settings' Outgoing fields and Account Settings' `user`) even though they
	are gone from the doctype meta; the query builder references them by column name.

	The values are copied verbatim — JMAP isn't reliably reachable during `bench migrate`,
	so identities can't be resolved here. The per-account default outgoing email is
	finalised against each account's identities by a background job once migrate is done.
	"""

	if frappe.db.has_column("User Settings", "default_outgoing_email") and frappe.db.has_column(
		"Account Settings", "user"
	):
		_copy_outgoing_settings()

	# Resolve each account's default outgoing email against its identities once migrate
	# is done — JMAP returns nothing while the migrate process is running.
	frappe.enqueue(backfill_default_outgoing_emails, queue="long", enqueue_after_commit=True)


def _copy_outgoing_settings() -> None:
	US = frappe.qb.DocType("User Settings")
	by_user = {
		row["user"]: row
		for row in (frappe.qb.from_(US).select(US.user, *(US[f] for f in OUTGOING_FIELDS)).run(as_dict=True))
	}

	if not by_user:
		return

	AS = frappe.qb.DocType("Account Settings")
	for settings in frappe.qb.from_(AS).select(AS.name, AS.user).run(as_dict=True):
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
