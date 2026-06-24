import frappe

from mail.api.sieve import regenerate_screening_sieve_for_all_accounts


def execute() -> None:
	"""Backfill the local-domain bypass into every screening-enabled account's sieve script.

	The screening gate now also trusts senders from any domain hosted on this server, but the scripts
	deployed before this change still have the old gate. Regenerating rebuilds and re-uploads them.
	Done in a background job once migrate is finished — the rebuild does JMAP round-trips, which aren't
	reachable while `bench migrate` is running.
	"""

	frappe.enqueue(
		regenerate_screening_sieve_for_all_accounts,
		queue="long",
		enqueue_after_commit=True,
	)
