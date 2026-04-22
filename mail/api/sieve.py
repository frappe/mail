import re

import frappe
from frappe import _

from mail.client.doctype.sieve_script.sieve_script import SieveScript
from mail.jmap import get_mailbox_id_by_name, get_mailbox_name_by_id, get_mailboxes

AUTOMATION_SCRIPT_NAME = "frappe_mail_automation"
AUTOMATION_SCRIPT_REQUIRE = 'require ["fileinto", "imap4flags"];'


@frappe.whitelist()
def get_sieve_scripts() -> list[dict]:
	"""Return all sieve scripts for the current user."""

	user = frappe.session.user
	script_ids = [s["id"] for s in SieveScript._fetch_sieve_scripts(user)[0]]
	return SieveScript._get_sieve_scripts(user, script_ids, True)


@frappe.whitelist()
def create_sieve_script(_name: str, content: str, active: bool) -> None:
	"""Create a new sieve script for the current user."""

	SieveScript._add_sieve_script(frappe.session.user, _name, content, active)


@frappe.whitelist()
def update_sieve_script(id: str, _name: str, content: str, active: bool = False) -> None:
	"""Update an existing sieve script for the current user."""

	SieveScript._update_sieve_script(frappe.session.user, id, _name, content, active)


@frappe.whitelist()
def delete_sieve_script(id: str) -> None:
	"""Delete a sieve script for the current user."""

	SieveScript._delete_sieve_scripts(frappe.session.user, [id])


@frappe.whitelist()
def create_automation_sieve_script(active: bool = False) -> str:
	"""Create the automation sieve script for the current user."""

	frappe.flags.allow_automation_script_creation = True
	return SieveScript._add_sieve_script(
		user=frappe.session.user,
		name=AUTOMATION_SCRIPT_NAME,
		content=AUTOMATION_SCRIPT_REQUIRE,
		active=active,
	)


def build_sieve_block(rules: dict, folder_path: str) -> str:
	"""Convert automation rules into a Sieve filter block.

	Args:
	    rules: Dictionary with keys:
	        - emails_from: comma-separated email addresses
	        - subject_contains: comma-separated keywords
	        - mark_as_read: boolean
	        - add_star: boolean
	        - match_if: 'any' or 'all'
	    folder_path: Destination folder path for matched emails.

	Returns:
	    Sieve filter block as a string, or empty string if no conditions.
	"""

	from_emails = [e.strip() for e in (rules.get("emails_from") or "").split(",") if e.strip()]
	subject_keywords = [k.strip() for k in (rules.get("subject_contains") or "").split(",") if k.strip()]

	if not from_emails and not subject_keywords:
		return ""

	conditions = []

	if from_emails:
		email_list = ", ".join(f'"{e}"' for e in from_emails)
		conditions.append(f'address :matches "from" [{email_list}]')

	if subject_keywords:
		keyword_list = ", ".join(f'"{k}"' for k in subject_keywords)
		conditions.append(f'header :contains "subject" [{keyword_list}]')

	use_allof = rules.get("match_if", "any") == "all"
	operator = "allof" if use_allof else "anyof"

	lines = [""]

	if len(conditions) == 1:
		lines.append(f"if {conditions[0]} {{")
	else:
		lines.append(f"if {operator} (")
		for i, condition in enumerate(conditions):
			suffix = "," if i < len(conditions) - 1 else ""
			lines.append(f"  {condition}{suffix}")
		lines.append(") {")

	lines.append(f'  fileinto "{folder_path}";')

	if rules.get("mark_as_read"):
		lines.append('  setflag "\\\\Seen";')

	if rules.get("add_star"):
		lines.append('  setflag "\\\\Flagged";')

	lines.append("  stop;")
	lines.append("}")

	return "\n".join(lines)


def strip_sieve_block(script: str, mailbox_name: str) -> str:
	"""Remove a Sieve filter block associated with the given mailbox name comment."""

	pattern = rf"# Mailbox: {re.escape(mailbox_name)}\n.*?stop;\n}}\n?"
	result = re.sub(pattern, "", script, flags=re.DOTALL)
	result = re.sub(r"\n{3,}", "\n\n", result)
	return result.rstrip() + "\n"


def append_sieve_block(script: str, mailbox_name: str, sieve_block: str) -> str:
	"""Append a labeled Sieve filter block to the script."""

	return script.rstrip() + "\n" + f"\n# Mailbox: {mailbox_name}{sieve_block}"


def rule_object_to_sieve(automation: dict, folder_path: str) -> str:
	"""Converts automation rules to Sieve script format.

	Args:
	        automation: Dictionary containing automation rules with keys:
	                - emails_from: comma-separated email addresses
	                - subject_contains: comma-separated keywords
	                - mark_as_read: boolean
	                - add_star: boolean
	                - match_if: 'any' or 'all'
	        folder_path: Name of the folder to file emails into

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


def remove_sieve_block(sieve_script: str, mailbox_name: str) -> str:
	"""Remove an entire Sieve filter block by its mailbox name comment."""

	pattern = rf"# Mailbox: {re.escape(mailbox_name)}\n.*?stop;\n}}\n?"
	result = re.sub(pattern, "", sieve_script, flags=re.DOTALL)
	result = re.sub(r"\n{3,}", "\n\n", result)
	result = result.rstrip() + "\n"

	return result


def get_automation_script_name() -> str:
	"""Return the name of the automation sieve script, creating it if absent."""

	user = frappe.session.user
	scripts = SieveScript._fetch_sieve_scripts(user, filter={"name": AUTOMATION_SCRIPT_NAME})

	if scripts and scripts[0]:
		return scripts[0][0]["name"]

	return f"{user}|{create_automation_sieve_script()}"


def sync_sieve_script_for_mailbox(
	mailbox_name: str,
	automation_rules: dict | None = None,
	previous_name: str | None = None,
) -> None:
	"""Rebuild the automation Sieve script to reflect the given mailbox's rules.

	Handles renaming (via `previous_name`), child mailbox rule preservation,
	and optional rule removal when `automation_rules` is None.
	"""

	script_name = get_automation_script_name()
	doc = frappe.get_doc("Sieve Script", script_name)

	# Rebuild blocks for all child mailboxes
	for child_name in set(get_child_mailbox_names(mailbox_name)):
		child_rules = extract_rules_from_script(doc.content, child_name)
		doc.content = strip_sieve_block(doc.content, child_name)

		if child_rules:
			child_folder_path = get_mailbox_folder_path(child_name, raise_exception=True)
			doc.content = append_sieve_block(
				doc.content, child_name, build_sieve_block(child_rules, child_folder_path)
			)

	# Remove the old block (handles rename or update)
	doc.content = strip_sieve_block(doc.content, previous_name or mailbox_name)

	# Add the new block if rules are provided
	if automation_rules:
		folder_path = get_mailbox_folder_path(mailbox_name, raise_exception=True)
		doc.content = append_sieve_block(
			doc.content, mailbox_name, build_sieve_block(automation_rules, folder_path)
		)

	doc.save()


def extract_rules_from_script(content: str, mailbox_name: str) -> dict | None:
	"""Parse and return the automation rules for a mailbox from a Sieve script.

	Returns None if no block is found for the given mailbox name.
	"""

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
		rules["emails_from"] = ", ".join(e.strip().replace('"', "") for e in emails_match.group(1).split(","))

	subject_match = re.search(r'header :contains "subject" \[(.*?)\]', block, re.DOTALL)
	if subject_match:
		rules["subject_contains"] = ", ".join(
			k.strip().replace('"', "") for k in subject_match.group(1).split(",")
		)

	if "allof" in block:
		rules["match_if"] = "all"
	elif "anyof" in block:
		rules["match_if"] = "any"

	rules["mark_as_read"] = 'setflag "\\\\Seen"' in block
	rules["add_star"] = 'setflag "\\\\Flagged"' in block

	return rules


def get_child_mailbox_names(parent_name: str) -> list[str]:
	"""Return the names of all direct child mailboxes for the given parent."""

	parent_id = get_mailbox_id_by_name(frappe.session.user, parent_name)
	mailboxes = get_mailboxes(frappe.session.user)

	return [m["_name"] for m in mailboxes if m.get("parent_id") == parent_id]


def get_mailbox_folder_path(name: str, raise_exception: bool = False) -> str | None:
	"""Return the full slash-separated folder path for a mailbox.

	Returns None if not found, or raises an exception if `raise_exception` is True.
	"""

	mailboxes = {m["_name"]: m for m in get_mailboxes(frappe.session.user)}

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
