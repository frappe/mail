import re
from contextlib import contextmanager

import frappe
from frappe import _

from mail.client.doctype.mailbox_settings.mailbox_settings import get_mailbox_automation_rules
from mail.client.doctype.screened_email_address.screened_email_address import (
	get_screened_email_addresses,
)
from mail.client.doctype.sieve_script.sieve_script import SieveScript
from mail.jmap import (
	get_mailbox_id_by_name,
	get_mailbox_id_by_role,
	get_mailbox_name_by_id,
	get_mailboxes,
	parse_account,
)
from mail.utils.user import get_account_emails, get_session_account

SCREENING_MAILBOX_NAME = "Screener"
AUTOMATION_SCRIPT_NAME = "frappe_mail_automation"
AUTOMATION_SCRIPT_REQUIRE = 'require ["fileinto", "imap4flags"];'


@frappe.whitelist()
def get_sieve_scripts(account_id: str) -> list[dict]:
	"""Return the sieve scripts for the account"""

	account = get_session_account(account_id)

	ids = [d["id"] for d in SieveScript._fetch_sieve_scripts(account)[0]]
	return SieveScript._get_sieve_scripts(account, ids, True)


@frappe.whitelist()
def create_sieve_script(account_id: str, _name: str, content: str, active: bool) -> None:
	"""Create a sieve script for the account"""

	account = get_session_account(account_id)

	SieveScript._add_sieve_script(account, _name, content, active)


@frappe.whitelist()
def update_sieve_script(account_id: str, id: str, _name: str, content: str, active: bool = False) -> None:
	"""Update a sieve script for the account"""

	account = get_session_account(account_id)

	SieveScript._update_sieve_script(account, id, _name, content, active)


@frappe.whitelist()
def delete_sieve_script(account_id: str, id: str) -> None:
	"""Delete a sieve script for the account"""

	account = get_session_account(account_id)

	SieveScript._delete_sieve_scripts(account, [id])


def rule_object_to_sieve(automation: dict, folder_path: str) -> str:
	"""Converts automation rules to Sieve script format.

	Args:
	        automation: Dictionary containing automation rules with keys:
	                - emails_from: comma-separated email addresses
	                - subject_contains: comma-separated keywords
	                - mark_as_read: boolean
	                - add_star: boolean
	                - match_if: 'any' or 'all'
	        folder_path: Full folder path to file emails into

	Returns:
	        Sieve script as a string
	"""

	emails_from = [
		email.strip() for email in (automation.get("emails_from") or "").split(",") if email.strip()
	]
	subject_contains = [
		keyword.strip()
		for keyword in (automation.get("subject_contains") or "").split(",")
		if keyword.strip()
	]

	if not emails_from and not subject_contains:
		return ""

	script_parts = [""]
	conditions = []

	if emails_from:
		email_list = ", ".join(f'"{email}"' for email in emails_from)
		conditions.append(f'address :matches "from" [{email_list}]')

	if subject_contains:
		keyword_list = ", ".join(f'"{keyword}"' for keyword in subject_contains)
		conditions.append(f'header :contains "subject" [{keyword_list}]')

	match_if = automation.get("match_if", "any")
	operator = "allof" if match_if == "all" else "anyof"

	if len(conditions) == 1:
		script_parts.append(f"if {conditions[0]} {{")
	else:
		script_parts.append(f"if {operator} (")
		for i, condition in enumerate(conditions):
			if i < len(conditions) - 1:
				script_parts.append(f"  {condition},")
			else:
				script_parts.append(f"  {condition}")
		script_parts.append(") {")

	if automation.get("mark_as_read"):
		script_parts.append('  addflag "\\\\Seen";')

	if automation.get("add_star"):
		script_parts.append('  addflag "\\\\Flagged";')

	script_parts.append(f'  fileinto "{folder_path}";')
	script_parts.append("  stop;")
	script_parts.append("}")

	return "\n".join(script_parts)


def remove_sieve_block(sieve_script: str, block_name: str) -> str:
	"""Remove an entire Sieve filter block by its block name comment."""

	pattern = rf"# {re.escape(block_name)}\n.*?stop;\n}}\n?"
	result = re.sub(pattern, "", sieve_script, flags=re.DOTALL)
	result = re.sub(r"\n{3,}", "\n\n", result)
	result = result.rstrip() + "\n"

	return result


@frappe.whitelist()
def create_automation_script(account_id: str, active: bool = False) -> None:
	"""Create (and optionally activate) the frappe_mail_automation sieve script for the account.

	Backs the "Enable Folder Automation" action. Delegates to `build_automation_sieve`, which creates
	the script if it doesn't exist and regenerates all four sections from their persistent backups
	(Mailbox Settings + Screened Email Address).
	"""

	build_automation_sieve(get_session_account(account_id), activate=active)


def get_automation_script_name(account: str) -> str:
	"""Return the name of the frappe_mail_automation sieve script, creating an empty one if missing.

	Only ensures the script exists (with a bare `require` statement); regenerating the automation
	blocks is `build_automation_sieve`'s job. Keeping creation free of any rebuild avoids re-entrancy,
	since the rebuild itself calls this to resolve the script it writes to.
	"""

	scripts = SieveScript._fetch_sieve_scripts(account, filter={"name": AUTOMATION_SCRIPT_NAME})
	if scripts and scripts[0]:
		return scripts[0][0]["name"]

	frappe.flags.allow_automation_script_creation = True
	script_id = SieveScript._add_sieve_script(account, AUTOMATION_SCRIPT_NAME, AUTOMATION_SCRIPT_REQUIRE)

	return f"{account}|{script_id}"


def append_sieve_block(script: str, block_name: str, sieve_block: str) -> str:
	"""Append a labeled Sieve filter block to the script."""

	return script.rstrip() + "\n" + f"\n# {block_name}{sieve_block}"


def backfill_mailbox_automation_rules() -> None:
	"""Backfill the Mailbox Settings automation backup from existing frappe_mail_automation scripts.

	Before the Mailbox Settings automation fields existed, folder rules lived only in the sieve script.
	Run as a background job (JMAP isn't reachable during `bench migrate`) so existing rules are captured
	into Mailbox Settings before a rebuild — which regenerates the script *from* Mailbox Settings —
	could drop them. Idempotent: re-running just rewrites the same backup.
	"""

	from mail.client.doctype.mailbox_settings.mailbox_settings import (
		automation_rules_to_settings,
		set_mailbox_settings,
	)
	from mail.jmap import get_jmap_connection

	for user in frappe.get_all("User Settings", filters={"username": ["is", "set"]}, pluck="user"):
		try:
			account_ids = list(get_jmap_connection(user, ignore_permissions=True).accounts.keys())
		except Exception:
			continue

		for account_id in account_ids:
			account = f"{user}:{account_id}"
			try:
				scripts = SieveScript._fetch_sieve_scripts(
					account, filter={"name": AUTOMATION_SCRIPT_NAME}
				)
				if not (scripts and scripts[0]):
					continue

				script = SieveScript._get_sieve_scripts(account, [scripts[0][0]["id"]], True)
				content = script[0]["content"] if script else ""
			except Exception:
				continue

			for mailbox in get_mailboxes(*parse_account(account)):
				rules = extract_rules_from_script(content, mailbox["_name"])
				if not rules or not (rules["emails_from"] or rules["subject_contains"]):
					continue

				try:
					set_mailbox_settings(
						account, mailbox["id"], **automation_rules_to_settings(rules)
					)
				except Exception:
					continue

	frappe.db.commit()


def extract_rules_from_script(content: str, mailbox_name: str) -> dict | None:
	"""Parse and return the automation rules for a mailbox from a Sieve script."""

	if not content or not mailbox_name:
		return None

	marker = f"# Mailbox: {mailbox_name}\n"
	marker_index = content.find(marker)
	if marker_index == -1:
		return None

	block_end = content.find("\n}", marker_index)
	if block_end == -1:
		return None

	block = content[marker_index : block_end + 2]
	rules = {
		"emails_from": "",
		"subject_contains": "",
		"match_if": "any",
		"mark_as_read": False,
		"add_star": False,
	}

	emails_match = re.search(r'address :matches "from" \[(.*?)\]', block, re.DOTALL)
	if emails_match:
		rules["emails_from"] = ", ".join(
			email.strip().replace('"', "") for email in emails_match.group(1).split(",")
		)

	subject_match = re.search(r'header :contains "subject" \[(.*?)\]', block, re.DOTALL)
	if subject_match:
		rules["subject_contains"] = ", ".join(
			keyword.strip().replace('"', "") for keyword in subject_match.group(1).split(",")
		)

	if "allof" in block:
		rules["match_if"] = "all"
	elif "anyof" in block:
		rules["match_if"] = "any"

	rules["mark_as_read"] = 'addflag "\\\\Seen"' in block
	rules["add_star"] = 'addflag "\\\\Flagged"' in block

	return rules


def get_mailbox_folder_path(account: str, name: str, raise_exception: bool = False) -> str | None:
	"""Return the full slash-separated folder path for a mailbox."""

	mailboxes = {mailbox["_name"]: mailbox for mailbox in get_mailboxes(*parse_account(account))}
	if name not in mailboxes:
		if raise_exception:
			frappe.throw(_("Mailbox with name '{0}' not found.").format(name))
		return None

	path_parts = []
	current = mailboxes[name]

	while current:
		path_parts.append(current["_name"])
		parent_id = current.get("parent_id")
		if not parent_id:
			break

		parent_name = get_mailbox_name_by_id(*parse_account(account), parent_id)
		current = mailboxes.get(parent_name)
		if current is None:
			if raise_exception:
				frappe.throw(_("Parent mailbox with name '{0}' not found.").format(parent_name))
			return None

	return "/".join(reversed(path_parts))


@contextmanager
def pause_automation_sieve_build():
	"""Suppress the automatic `build_automation_sieve` triggered by Mailbox Settings / Screened Email
	Address document hooks, so a caller doing several writes rebuilds the script once at the end
	instead of after every write.

	Use it around bulk writes, then call `build_automation_sieve` yourself once::

	    with pause_automation_sieve_build():
	            ...several saves...
	    build_automation_sieve(account)
	"""

	previous = frappe.flags.get("skip_automation_sieve_build")
	frappe.flags.skip_automation_sieve_build = True
	try:
		yield
	finally:
		frappe.flags.skip_automation_sieve_build = previous


def maybe_build_automation_sieve(account: str) -> None:
	"""Build the automation sieve from a document hook unless a caller paused builds for a bulk write."""

	if frappe.flags.get("skip_automation_sieve_build"):
		return

	build_automation_sieve(account)


def build_automation_sieve(account: str, activate: bool = False) -> None:
	"""Build the entire frappe_mail_automation sieve script from its sources of truth.

	This is the single entry point for (re)generating the automation script. It:
	  1. Ensures the frappe_mail_automation script exists, creating an empty one if a third-party
	     client deleted it.
	  2. Regenerates all four managed sections, in precedence order — Reject → Mailbox → Spam →
	     Screening — from their persistent backups: the per-mailbox rules in Mailbox Settings (Mailbox
	     section) and the Reject/Spam/Screening rules in Screened Email Address plus Account Settings.
	  3. Activates the script when `activate` is set (the "Enable Folder Automation" action); otherwise
	     its current active state is preserved.

	Building from the backups rather than mutating the existing script makes it idempotent and recovers
	the script after a third-party client deletes or mangles it.
	"""

	doc = frappe.get_doc("Sieve Script", get_automation_script_name(account))
	doc.content = _build_automation_content(account)
	if activate:
		doc.active = True
	doc.save()


def _build_automation_content(account: str) -> str:
	"""Generate the full frappe_mail_automation script content from the persistent backups."""

	content = AUTOMATION_SCRIPT_REQUIRE + "\n"

	# Mailbox section: one block per mailbox that has automation rules in Mailbox Settings.
	for mailbox in get_mailboxes(*parse_account(account)):
		rules = get_mailbox_automation_rules(account, mailbox["id"])
		if not rules:
			continue

		folder_path = get_mailbox_folder_path(account, mailbox["_name"], raise_exception=True)
		block = rule_object_to_sieve(rules, folder_path)
		if block:
			content = append_sieve_block(content, f"Mailbox: {mailbox['_name']}", block)

	# Reject / Spam / Screening sections, layered on top of the mailbox rules.
	content = _apply_screening_blocks(account, content)

	return content.rstrip() + "\n"


@frappe.whitelist()
def rebuild_automation_script_for_account(account_id: str) -> None:
	"""Rebuild the frappe_mail_automation script from its backups for the session account.

	Backs the manual "Rebuild Automation" action, for when the script was deleted or edited by a
	third-party client.
	"""

	build_automation_sieve(get_session_account(account_id))


def get_junk_folder_path(account: str) -> str:
	"""Return the folder path of the account's Junk mailbox (for sieve `fileinto`)."""

	junk_id = get_mailbox_id_by_role(
		*parse_account(account), "junk", create_if_not_exists=True, raise_exception=True
	)
	junk_name = get_mailbox_name_by_id(*parse_account(account), junk_id, raise_exception=True)
	return get_mailbox_folder_path(account, junk_name, raise_exception=True)


def get_screening_folder_path(account: str) -> str:
	"""Return the folder path of the account's Screening mailbox, creating it if missing.

	Screening is not a standard JMAP role, so it is a plain named mailbox looked up by name.
	"""

	from mail.client.doctype.mailbox.mailbox import add_mailbox
	from mail.jmap.services.core import CoreService

	user, account_id = parse_account(account)

	# The mailbox list lives in a per-process TTL cache, so a negative lookup can be stale — another
	# worker may already have created the Screener. Refresh from the server before deciding to create,
	# so we never try to recreate an existing mailbox (which JMAP rejects with "already exists").
	CoreService.invalidate_cache(account_id, key="mailboxes")
	if not get_mailbox_id_by_name(user, account_id, SCREENING_MAILBOX_NAME):
		add_mailbox(account, SCREENING_MAILBOX_NAME)
		CoreService.invalidate_cache(account_id, key="mailboxes")

	return get_mailbox_folder_path(account, SCREENING_MAILBOX_NAME, raise_exception=True)


def is_screening_enabled(account: str) -> bool:
	"""Whether Hey-style screening is enabled for the account (Account Settings.enable_screening)."""

	return bool(frappe.db.get_value("Account Settings", parse_account(account)[1], "enable_screening"))


def build_screening_gate(account: str, accepted_emails: list[str]) -> str:
	"""Build the screening gate: file mail from senders not on the accepted list into Screening.

	The account's own identity emails are always trusted, so self-addressed and identity mail is
	never screened. This block is the last in the script — the catch-all fallback after Reject, Spam,
	and the mailbox automation rules — so trusted and folder-routed mail is handled before it, and only
	mail from an unrecognised sender that nothing else matched falls into Screening.
	"""

	screening_folder_path = get_screening_folder_path(account)

	try:
		own_emails = get_account_emails(account)
	except Exception:
		own_emails = []

	trusted = list(dict.fromkeys(e.strip() for e in [*accepted_emails, *own_emails] if e and e.strip()))

	if trusted:
		joined = ",\n  ".join(f'"{e}"' for e in trusted)
		condition_block = f'if not address :is "from" [\n  {joined}\n] {{'
	else:
		# Nothing trusted yet → screen everything (only reached after the Reject/Spam blocks).
		condition_block = 'if exists "from" {'

	return "\n".join(
		[
			"# Screening",
			condition_block,
			f'  fileinto "{screening_folder_path}";',
			"  stop;",
			"}",
			"\n",
		]
	)


def _build_screening_block(block_name: str, emails: list[str], action_lines: list[str]) -> str:
	"""Build a labeled sieve block matching the given senders and running `action_lines`.

	Returns an empty string when there are no senders to match.
	"""

	conditions = [f'address :is "from" "{e.strip()}"' for e in emails if e and e.strip()]
	if not conditions:
		return ""

	if len(conditions) == 1:
		condition_block = f"if {conditions[0]} {{"
	else:
		joined = ",\n  ".join(conditions)
		condition_block = f"if anyof (\n  {joined}\n) {{"

	return "\n".join([f"# {block_name}", condition_block, *action_lines, "}", "\n"])


def _apply_screening_blocks(account: str, content: str) -> str:
	"""Layer the Reject/Spam/Screening sieve blocks onto `content` and return the result.

	Rebuilt from the Screened Email Address list (+ Account Settings) in one pass. The blocks are
	ordered by precedence: Reject (discard) sits at the very top, right after `require`, so it wins
	outright. The mailbox automation rules come next, so an explicit folder rule can still route mail.
	Spam (file to Junk) and the Screening gate (`if not <trusted>` → Screening) are fallbacks below the
	mailbox rules — Spam first, then the catch-all Screening gate at the very bottom. The final order is
	Reject → Mailbox → Spam → Screening. A sender has at most one screening rule (uniqueness is on the
	address), so the blocks never conflict.
	"""

	content = (content or "").lstrip()

	# Remove any existing screening blocks, including the legacy block names from the pre-merge
	# "Blocked Email Address" / "Junk Email Address" doctypes, so old scripts get cleaned up.
	for name in ("Rejected Emails", "Spam Senders", "Screening", "Blocked Emails", "Junk Senders"):
		content = remove_sieve_block(content, name)

	screened = get_screened_email_addresses(account)
	reject_emails = [s.email for s in screened if s.action == "Reject"]
	spam_emails = [s.email for s in screened if s.action == "Spam"]
	accepted_emails = [s.email for s in screened if s.action == "Accepted"]

	# Reject is the most aggressive action and must win outright, so it sits at the very top — right
	# after the require statement(s), above the mailbox rules.
	reject_block = _build_screening_block("Rejected Emails", reject_emails, ["  discard;", "  stop;"])
	if reject_block:
		require_pattern = r"^(require\s+\[.*?\];\s*)+"
		match = re.match(require_pattern, content, flags=re.DOTALL)
		if match:
			insert_pos = match.end()
			content = content[:insert_pos] + "\n" + reject_block + content[insert_pos:]
		else:
			content = reject_block + content

	# Spam goes below the mailbox rules (so an explicit folder rule can still claim the mail) but above
	# the Screening gate.
	if spam_emails:
		junk_folder_path = get_junk_folder_path(account)
		spam_block = _build_screening_block(
			"Spam Senders",
			spam_emails,
			# Flag as junk ($junk keyword) as well as filing into Junk, so the mail is marked junk — not
			# just located there — matching what marking a mail as junk does.
			['  addflag "$junk";', f'  fileinto "{junk_folder_path}";', "  stop;"],
		)
		if spam_block:
			content = content.rstrip() + "\n\n" + spam_block.rstrip() + "\n"

	# Append the Screening gate last — the catch-all fallback, below every other block.
	if is_screening_enabled(account):
		gate = build_screening_gate(account, accepted_emails)
		content = content.rstrip() + "\n\n" + gate.rstrip() + "\n"

	return content.rstrip() + "\n"


def update_sieve_script_for_mailbox(account: str, name: str | None = None, old_name: str | None = None) -> None:
	"""Deprecated shim — use `build_automation_sieve`. Kept until all callers are migrated."""

	build_automation_sieve(account)
