import re

import frappe

from mail.client.doctype.blocked_email_address.blocked_email_address import get_blocked_email_addresses
from mail.client.doctype.sieve_script.sieve_script import SieveScript


@frappe.whitelist()
def get_sieve_scripts() -> list[dict]:
	"""Return the sieve scripts for the user"""

	user = frappe.session.user
	ids = [d["id"] for d in SieveScript._fetch_sieve_scripts(user)[0]]
	return SieveScript._get_sieve_scripts(user, ids, True)


@frappe.whitelist()
def create_sieve_script(_name: str, content: str, active: bool) -> None:
	"""Create a sieve script for the user"""

	SieveScript._add_sieve_script(frappe.session.user, _name, content, active)


@frappe.whitelist()
def update_sieve_script(id: str, _name: str, content: str, active: bool = False) -> None:
	"""Update a sieve script for the user"""

	SieveScript._update_sieve_script(frappe.session.user, id, _name, content, active)


@frappe.whitelist()
def delete_sieve_script(id: str) -> None:
	"""Delete a sieve script for the user"""

	SieveScript._delete_sieve_scripts(frappe.session.user, [id])


def rule_object_to_sieve(automation: dict, folder_name: str) -> str:
	"""Converts automation rules to Sieve script format.

	Args:
	        automation: Dictionary containing automation rules with keys:
	                - emails_from: comma-separated email addresses
	                - subject_contains: comma-separated keywords
	                - mark_as_read: boolean
	                - add_star: boolean
	                - match_if: 'any' or 'all'
	        folder_name: Name of the folder to file emails into

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

	script_parts.append(f'  fileinto "{folder_name}";')

	if automation.get("mark_as_read"):
		script_parts.append('  setflag "\\\\Seen";')

	if automation.get("add_star"):
		script_parts.append('  setflag "\\\\Flagged";')

	script_parts.append("  stop;")
	script_parts.append("}")

	return "\n".join(script_parts)


def remove_sieve_block(sieve_script: str, mailbox_name: str) -> str:
	"""Remove an entire Sieve filter block by its mailbox name comment."""

	pattern = rf"# {re.escape(mailbox_name)}\n.*?stop;\n}}\n?"
	result = re.sub(pattern, "", sieve_script, flags=re.DOTALL)
	result = re.sub(r"\n{3,}", "\n\n", result)
	result = result.rstrip() + "\n"

	return result


@frappe.whitelist()
def create_automation_script(active: bool = False) -> str:
	"""Create the frappe_mail_automation sieve script for the user."""

	frappe.flags.allow_automation_script_creation = True
	return SieveScript._add_sieve_script(
		user=frappe.session.user,
		name="frappe_mail_automation",
		content='require ["fileinto", "imap4flags"];',
		active=active,
	)


def get_automation_script_name(user: str) -> str:
	"""Returns the name of the frappe_mail_automation sieve script for the user, creating it if it doesn't exist."""

	scripts = SieveScript._fetch_sieve_scripts(user, filter={"name": "frappe_mail_automation"})
	if scripts and scripts[0]:
		return scripts[0][0]["name"]

	script_name = create_automation_script()

	return f"{user}|{script_name}"


def update_sieve_script_for_mailbox(
	name: str, automation_rules: dict | None = None, old_name: str | None = None
) -> None:
	"""Updates the Sieve script for the given mailbox based on the provided automation rules."""

	user = frappe.session.user
	automation_script_name = get_automation_script_name(user)
	doc = frappe.get_doc("Sieve Script", automation_script_name)
	doc.content = remove_sieve_block(doc.content, f"Mailbox: {old_name or name}")

	if automation_rules:
		mailbox_rule_set = rule_object_to_sieve(automation_rules, name)
		doc.content = doc.content.rstrip() + "\n"
		doc.content += f"\n# Mailbox: {name}{mailbox_rule_set}"

	doc.save()


def update_sieve_script_for_blocked_emails(user: str) -> None:
	"""Update sieve script to block emails from blocked email list at the top."""

	automation_script_name = get_automation_script_name(user)
	doc = frappe.get_doc("Sieve Script", automation_script_name)
	content = (doc.content or "").lstrip()

	block_name = "Blocked Emails"
	content = remove_sieve_block(content, block_name)

	blocked_emails = get_blocked_email_addresses(user)
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
