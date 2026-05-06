import re

import frappe
from frappe import _

from mail.client.doctype.blocked_email_address.blocked_email_address import get_blocked_email_addresses
from mail.client.doctype.sieve_script.sieve_script import SieveScript
from mail.jmap import get_mailbox_id_by_name, get_mailbox_name_by_id, get_mailboxes

AUTOMATION_SCRIPT_NAME = "frappe_mail_automation"
AUTOMATION_SCRIPT_REQUIRE = 'require ["fileinto", "imap4flags"];'


@frappe.whitelist()
def get_sieve_scripts(account: str) -> list[dict]:
	"""Return the sieve scripts for the user"""

	ids = [d["id"] for d in SieveScript._fetch_sieve_scripts(account)[0]]
	return SieveScript._get_sieve_scripts(account, ids, True)


@frappe.whitelist()
def create_sieve_script(account: str, _name: str, content: str, active: bool) -> None:
	"""Create a sieve script for the user"""

	SieveScript._add_sieve_script(account, _name, content, active)


@frappe.whitelist()
def update_sieve_script(account: str, id: str, _name: str, content: str, active: bool = False) -> None:
	"""Update a sieve script for the user"""

	SieveScript._update_sieve_script(account, id, _name, content, active)


@frappe.whitelist()
def delete_sieve_script(account: str, id: str) -> None:
	"""Delete a sieve script for the user"""

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

	script_parts.append(f'  fileinto "{folder_path}";')

	if automation.get("mark_as_read"):
		script_parts.append('  setflag "\\\\Seen";')

	if automation.get("add_star"):
		script_parts.append('  setflag "\\\\Flagged";')

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
def create_automation_script(account: str, active: bool = False) -> str:
	"""Create the frappe_mail_automation sieve script for the user."""

	frappe.flags.allow_automation_script_creation = True
	return SieveScript._add_sieve_script(
		account=account,
		name=AUTOMATION_SCRIPT_NAME,
		content=AUTOMATION_SCRIPT_REQUIRE,
		active=active,
	)


def get_automation_script_name(account: str) -> str:
	"""Returns the name of the frappe_mail_automation sieve script for the user, creating it if it doesn't exist."""

	scripts = SieveScript._fetch_sieve_scripts(account, filter={"name": AUTOMATION_SCRIPT_NAME})
	if scripts and scripts[0]:
		return scripts[0][0]["name"]

	script_name = create_automation_script(account)

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

	rules["mark_as_read"] = 'setflag "\\\\Seen"' in block
	rules["add_star"] = 'setflag "\\\\Flagged"' in block

	return rules


def get_child_mailbox_names(account: str, parent_name: str) -> list[str]:
	"""Return the names of all direct child mailboxes for the given parent."""

	parent_id = get_mailbox_id_by_name(frappe.session.user, parent_name)
	mailboxes = get_mailboxes(account)
	return [mailbox["_name"] for mailbox in mailboxes if mailbox.get("parent_id") == parent_id]


def get_mailbox_folder_path(name: str, raise_exception: bool = False) -> str | None:
	"""Return the full slash-separated folder path for a mailbox."""

	mailboxes = {mailbox["_name"]: mailbox for mailbox in get_mailboxes(frappe.session.user)}
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

		parent_name = get_mailbox_name_by_id(frappe.session.user, parent_id)
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
			child_folder_path = get_mailbox_folder_path(child_name, raise_exception=True)
			doc.content = append_sieve_block(
				doc.content, child_block_name, rule_object_to_sieve(child_rules, child_folder_path)
			)

	doc.content = remove_sieve_block(doc.content, f"Mailbox: {old_name or name}")

	if automation_rules:
		folder_path = get_mailbox_folder_path(name, raise_exception=True)
		doc.content = append_sieve_block(
			doc.content, f"Mailbox: {name}", rule_object_to_sieve(automation_rules, folder_path)
		)

	doc.save()


def update_sieve_script_for_blocked_emails(account: str) -> None:
	"""Update sieve script to block emails from blocked email list at the top."""

	automation_script_name = get_automation_script_name(account)
	doc = frappe.get_doc("Sieve Script", automation_script_name)
	content = (doc.content or "").lstrip()

	block_name = "Blocked Emails"
	content = remove_sieve_block(content, block_name)

	blocked_emails = get_blocked_email_addresses(frappe.session.user)
	conditions = [f'address :is "from" "{e.strip()}"' for e in blocked_emails if e.strip()]

	if not conditions:
		doc.content = content.rstrip() + "\n"
		doc.save()
		return

	if len(conditions) == 1:
		condition_block = f"if {conditions[0]} {{"
	else:
		joined = ",\n  ".join(conditions)
		condition_block = f"if anyof (\n  {joined}\n) {{"

	block_script = "\n".join(
		[
			f"# {block_name}",
			condition_block,
			"  discard;",
			"  stop;",
			"}",
			"\n",
		]
	)

	require_pattern = r"^(require\s+\[.*?\];\s*)+"
	match = re.match(require_pattern, content, flags=re.DOTALL)

	if match:
		insert_pos = match.end()
		content = content[:insert_pos] + "\n" + block_script + content[insert_pos:]
	else:
		content = block_script + content

	doc.content = content.rstrip() + "\n"
	doc.save()
