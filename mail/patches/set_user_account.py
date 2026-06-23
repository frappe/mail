def execute() -> None:
	"""Obsolete: backfilled the per-user `account` (user:account_id) handle on several client
	doctypes.

	Every doctype it targeted (Mail Exchange, Mail Queue, Mail Sync History, Mailbox Settings,
	Blocked Email Address) was later reshaped to key on a bare `account_id`, dropping the `account`
	column this patch wrote to. It already ran on existing sites; there is nothing left to do.
	"""

	return
