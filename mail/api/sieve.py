import re

import frappe
from frappe import _

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


def _extract_sieve_block(sieve_script: str, block_name: str) -> str | None:
	"""Return a labeled Sieve block's text (with its `# {block_name}` header), or None if absent."""

	pattern = rf"# {re.escape(block_name)}\n.*?stop;\n}}\n?"
	match = re.search(pattern, sieve_script, flags=re.DOTALL)
	return match.group(0) if match else None


def _move_screening_gate_to_bottom(content: str) -> str:
	"""Move the Screening gate block to the end of the script (no-op if there isn't one).

	The gate matches `if not <trusted>`, so it's a catch-all fallback and must stay below every other
	block — Reject, Spam, and the mailbox rules — including any appended after it.
	"""

	block = _extract_sieve_block(content, "Screening")
	if not block:
		return content

	content = remove_sieve_block(content, "Screening")
	return content.rstrip() + "\n\n" + block.rstrip() + "\n"


@frappe.whitelist()
def create_automation_script(account_id: str, active: bool = False) -> str:
	"""Create the frappe_mail_automation sieve script for the account."""

	account = get_session_account(account_id)

	frappe.flags.allow_automation_script_creation = True
	return SieveScript._add_sieve_script(
		account=account,
		name=AUTOMATION_SCRIPT_NAME,
		content=AUTOMATION_SCRIPT_REQUIRE,
		active=active,
	)


def get_automation_script_name(account: str) -> str:
	"""Returns the name of the frappe_mail_automation sieve script for the account, creating it if it doesn't exist."""

	scripts = SieveScript._fetch_sieve_scripts(account, filter={"name": AUTOMATION_SCRIPT_NAME})
	if scripts and scripts[0]:
		return scripts[0][0]["name"]

	# `create_automation_script` takes the bare account_id (it reconstructs the session handle
	# itself); pass the full `account` handle through and it would get double-prefixed.
	script_name = create_automation_script(parse_account(account)[1])

	return f"{account}|{script_name}"


def append_sieve_block(script: str, block_name: str, sieve_block: str) -> str:
	"""Append a labeled Sieve filter block to the script."""

	return script.rstrip() + "\n" + f"\n# {block_name}{sieve_block}"


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


def get_child_mailbox_names(account: str, parent_name: str) -> list[str]:
	"""Return the names of all direct child mailboxes for the given parent."""

	parent_id = get_mailbox_id_by_name(*parse_account(account), parent_name)
	mailboxes = get_mailboxes(*parse_account(account))
	return [mailbox["_name"] for mailbox in mailboxes if mailbox.get("parent_id") == parent_id]


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


def update_sieve_script_for_mailbox(
	account: str, name: str, automation_rules: dict | None = None, old_name: str | None = None
) -> None:
	"""Update the automation Sieve script for a mailbox and its direct children."""

	automation_script_name = get_automation_script_name(account)
	doc = frappe.get_doc("Sieve Script", automation_script_name)

	for child_name in set(get_child_mailbox_names(account, name)):
		child_block_name = f"Mailbox: {child_name}"
		child_rules = extract_rules_from_script(doc.content, child_name)
		doc.content = remove_sieve_block(doc.content, child_block_name)

		if child_rules:
			child_folder_path = get_mailbox_folder_path(account, child_name, raise_exception=True)
			doc.content = append_sieve_block(
				doc.content, child_block_name, rule_object_to_sieve(child_rules, child_folder_path)
			)

	doc.content = remove_sieve_block(doc.content, f"Mailbox: {old_name or name}")

	if automation_rules:
		folder_path = get_mailbox_folder_path(account, name, raise_exception=True)
		doc.content = append_sieve_block(
			doc.content, f"Mailbox: {name}", rule_object_to_sieve(automation_rules, folder_path)
		)

	# Mailbox blocks are appended to the end, so push the Screening fallback back below them.
	doc.content = _move_screening_gate_to_bottom(doc.content)

	doc.save()


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

	if not get_mailbox_id_by_name(*parse_account(account), SCREENING_MAILBOX_NAME):
		add_mailbox(account, SCREENING_MAILBOX_NAME)

	return get_mailbox_folder_path(account, SCREENING_MAILBOX_NAME, raise_exception=True)


def is_screening_enabled(account: str) -> bool:
	"""Whether Hey-style screening is enabled for the account (Account Settings.enable_screening)."""

	return bool(frappe.db.get_value("Account Settings", {"account": account}, "enable_screening"))


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


def update_sieve_script_for_screened_emails(account: str) -> None:
	"""Regenerate the screening sieve blocks in the automation script.

	Rebuilt from the Screened Email Address list (+ Account Settings) in one pass. Reject (discard) and
	Spam (file to Junk) are the "screen out" group and go at the top, right after `require`, so they're
	tested before any routing. The Screening gate (`if not <trusted>` → Screening) is a catch-all
	fallback, so it's appended at the very bottom — below the mailbox automation rules — and only
	reached once Reject, Spam, and every folder rule have been tested and didn't match. A sender has at
	most one screening rule (uniqueness is on the address), so the blocks never conflict.
	"""

	automation_script_name = get_automation_script_name(account)
	doc = frappe.get_doc("Sieve Script", automation_script_name)
	content = (doc.content or "").lstrip()

	# Remove existing screening blocks, including the legacy block names from the pre-merge
	# "Blocked Email Address" / "Junk Email Address" doctypes, so old scripts get cleaned up.
	for name in ("Rejected Emails", "Spam Senders", "Screening", "Blocked Emails", "Junk Senders"):
		content = remove_sieve_block(content, name)

	screened = get_screened_email_addresses(account)
	reject_emails = [s.email for s in screened if s.action == "Reject"]
	spam_emails = [s.email for s in screened if s.action == "Spam"]
	accepted_emails = [s.email for s in screened if s.action == "Accepted"]

	# Reject is the more aggressive action, so its block comes first within the screen-out group.
	top_blocks = []
	reject_block = _build_screening_block("Rejected Emails", reject_emails, ["  discard;", "  stop;"])
	if reject_block:
		top_blocks.append(reject_block)

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
			top_blocks.append(spam_block)

	# Insert Reject/Spam right after the require statement(s), above the mailbox rules.
	if top_blocks:
		block_script = "".join(top_blocks)
		require_pattern = r"^(require\s+\[.*?\];\s*)+"
		match = re.match(require_pattern, content, flags=re.DOTALL)
		if match:
			insert_pos = match.end()
			content = content[:insert_pos] + "\n" + block_script + content[insert_pos:]
		else:
			content = block_script + content

	# Append the Screening gate last — the catch-all fallback, below every mailbox rule.
	if is_screening_enabled(account):
		gate = build_screening_gate(account, accepted_emails)
		content = content.rstrip() + "\n\n" + gate.rstrip() + "\n"

	doc.content = content.rstrip() + "\n"
	doc.save()
