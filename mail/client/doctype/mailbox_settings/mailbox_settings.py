# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document

from mail.jmap import parse_account
from mail.utils.user import is_system_manager


class MailboxSettings(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_duplicate()

	def before_insert(self) -> None:
		self.user = parse_account(self.account)[0]

	def validate_duplicate(self) -> None:
		"""Checks for duplicate Mailbox Settings for the same account and mailbox ID."""

		existing = frappe.db.exists(
			"Mailbox Settings",
			{
				"account": self.account,
				"mailbox_id": self.mailbox_id,
				"name": ["!=", self.name],
			},
		)

		if existing:
			frappe.throw(
				_("Mailbox Settings for account {0} with mailbox ID {1} already exists.").format(
					frappe.bold(self.account), frappe.bold(self.mailbox_id)
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

	if settings := frappe.db.get_value("Mailbox Settings", {"account": account, "mailbox_id": mailbox_id}):
		return frappe.get_doc("Mailbox Settings", settings)

	if raise_exception:
		frappe.throw(
			_("Mailbox Settings for account {0} with mailbox ID {1} not found.").format(
				frappe.bold(account), frappe.bold(mailbox_id)
			)
		)


def set_mailbox_settings(account: str, mailbox_id: str, **kwargs) -> None:
	"""Sets the Mailbox Settings for a given account and mailbox ID. Creates a new document if it doesn't exist."""

	settings = get_mailbox_settings(account, mailbox_id, raise_exception=False)

	if not settings:
		settings = frappe.new_doc("Mailbox Settings")
		settings.account = account
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
	frappe.db.add_unique(
		"Mailbox Settings", ["account", "mailbox_id"], constraint_name="unique_account_mailbox"
	)


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	return f"(`tabMailbox Settings`.user = '{user}')"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mailbox Settings":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True

	return doc.user == user
