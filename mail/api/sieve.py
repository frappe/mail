import re

import frappe

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
		mailbox_id: Optional mailbox ID for reference

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

	pattern = rf"# Mailbox: {re.escape(mailbox_name)}\n.*?stop;\n}}\n?"
	result = re.sub(pattern, "", sieve_script, flags=re.DOTALL)
	result = re.sub(r"\n{3,}", "\n\n", result)
	result = result.rstrip() + "\n"

	return result


def update_sieve_script_for_mailbox(
	name: str, automation_rules: dict | None = None, old_name: str | None = None
) -> None:
	"""Updates the Sieve script for the given mailbox based on the provided automation rules."""

	automation_script_name = SieveScript._fetch_sieve_scripts(
		frappe.session.user, filter={"name": "frappe_mail_automation"}
	)[0][0]["name"]
	doc = frappe.get_doc("Sieve Script", automation_script_name)
	doc.content = remove_sieve_block(doc.content, old_name or name)

	if automation_rules:
		mailbox_rule_set = rule_object_to_sieve(automation_rules, name)
		doc.content = doc.content.rstrip() + "\n"
		doc.content += f"\n# Mailbox: {name}{mailbox_rule_set}"

	doc.save()
