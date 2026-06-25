# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document

from mail.jmap import parse_account
from mail.utils.user import get_account_scoped_permission_query, has_account_scoped_permission


class MailboxSettings(Document):
	"""Per-mailbox settings, shared per JMAP account ID — every user with access to the
	account sees the same mailbox icons, colors, and push-notification preferences."""

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_duplicate()

	def validate_duplicate(self) -> None:
		"""Checks for duplicate Mailbox Settings for the same account and mailbox ID."""

		existing = frappe.db.exists(
			"Mailbox Settings",
			{
				"account_id": self.account_id,
				"mailbox_id": self.mailbox_id,
				"name": ["!=", self.name],
			},
		)

		if existing:
			frappe.throw(
				_("Mailbox Settings for account {0} with mailbox ID {1} already exists.").format(
					frappe.bold(self.account_id), frappe.bold(self.mailbox_id)
				),
				title=_("Duplicate Mailbox Settings"),
			)

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


def get_mailbox_settings(
	account: str, mailbox_id: str, raise_exception: bool = True
) -> MailboxSettings | None:
	"""Fetches the Mailbox Settings for a given account and mailbox ID."""

	account_id = parse_account(account)[1]
	if settings := frappe.db.get_value(
		"Mailbox Settings", {"account_id": account_id, "mailbox_id": mailbox_id}
	):
		return frappe.get_doc("Mailbox Settings", settings)

	if raise_exception:
		frappe.throw(
			_("Mailbox Settings for account {0} with mailbox ID {1} not found.").format(
				frappe.bold(account), frappe.bold(mailbox_id)
			)
		)


def get_mailbox_automation_rules(account: str, mailbox_id: str) -> dict | None:
	"""Return the persisted automation rules for a mailbox as a rule dict, or None if it has none.

	This is the backup that the frappe_mail_automation Sieve script is generated from, so the script
	can be rebuilt even if a third-party client deletes it. A mailbox is considered to have no
	automation when neither a sender nor a subject condition is set.
	"""

	settings = get_mailbox_settings(account, mailbox_id, raise_exception=False)
	if not settings or not (settings.emails_from or settings.subject_contains):
		return None

	return {
		"emails_from": settings.emails_from or "",
		"subject_contains": settings.subject_contains or "",
		"match_if": settings.match_if or "any",
		"mark_as_read": bool(settings.mark_as_read),
		"add_star": bool(settings.add_star),
	}


def automation_rules_to_settings(rules: dict | None) -> dict:
	"""Flatten a rule dict (or None) into the Mailbox Settings automation fields.

	A falsy `rules` clears the fields, so removing a mailbox's automation in the UI also clears its
	backup.
	"""

	rules = rules or {}
	return {
		"emails_from": rules.get("emails_from") or "",
		"subject_contains": rules.get("subject_contains") or "",
		"match_if": rules.get("match_if") or "any",
		"mark_as_read": 1 if rules.get("mark_as_read") else 0,
		"add_star": 1 if rules.get("add_star") else 0,
	}


def set_mailbox_settings(account: str, mailbox_id: str, **kwargs) -> None:
	"""Sets the Mailbox Settings for a given account and mailbox ID. Creates a new document if it doesn't exist."""

	settings = get_mailbox_settings(account, mailbox_id, raise_exception=False)

	if not settings:
		settings = frappe.new_doc("Mailbox Settings")
		settings.account_id = parse_account(account)[1]
		settings.mailbox_id = mailbox_id
		settings.insert()

	mailbox_fields = ["subscribed", "parent", "_name", "role", "sort_order"]
	filtered_kwargs = {k: v for k, v in kwargs.items() if k not in mailbox_fields}

	if filtered_kwargs:
		settings._db_set(**filtered_kwargs)

	if any(field in kwargs for field in mailbox_fields):
		mailbox = frappe.get_doc("Mailbox", f"{account}|{mailbox_id}")
		for field in mailbox_fields:
			if field in kwargs:
				setattr(mailbox, field, kwargs[field])
		mailbox.save()


def on_doctype_update() -> None:
	# Mailbox settings are shared per account_id, so uniqueness is on (account_id, mailbox_id).
	frappe.db.add_unique(
		"Mailbox Settings", ["account_id", "mailbox_id"], constraint_name="unique_account_id_mailbox"
	)


def get_permission_query_condition(user: str | None = None) -> str:
	return get_account_scoped_permission_query("Mailbox Settings", user=user)


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mailbox Settings":
		return False

	return has_account_scoped_permission(doc, user=user)
