# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from mail.utils.user import is_system_manager
from mail.utils.cache import get_user_owned_domains
from mail.utils.validation import (
	validate_active_domain,
	is_valid_email_for_domain,
	validate_mailbox_for_incoming,
)


class MailAlias(Document):
	def autoname(self) -> None:
		self.alias = self.alias.strip().lower()
		self.name = self.alias

	def validate(self) -> None:
		self.validate_email()
		self.validate_domain()
		self.validate_mailboxes()

	def validate_email(self) -> None:
		"""Validates the email address."""

		is_valid_email_for_domain(self.alias, self.domain_name, raise_exception=True)

	def validate_domain(self) -> None:
		"""Validates the domain."""

		validate_active_domain(self.domain_name)

	def validate_mailboxes(self) -> None:
		"""Validates the mailboxes."""

		mailboxes = []

		for mailbox in self.mailboxes:
			if mailbox.mailbox == self.alias:
				frappe.throw(
					_("Row #{0}: Mailbox cannot be the same as the alias.").format(mailbox.idx)
				)
			elif mailbox.mailbox in mailboxes:
				frappe.throw(
					_("Row #{0}: Duplicate mailbox {1}.").format(
						mailbox.idx, frappe.bold(mailbox.mailbox)
					)
				)

			validate_mailbox_for_incoming(mailbox.mailbox)
			mailboxes.append(mailbox.mailbox)


def has_permission(doc: "Document", ptype: str, user: str) -> bool:
	if doc.doctype != "Mail Alias":
		return False

	return is_system_manager(user) or (doc.domain_name in get_user_owned_domains(user))


def get_permission_query_condition(user: str | None = None) -> str:
	if not user:
		user = frappe.session.user

	if is_system_manager(user):
		return ""

	if domains := ", ".join(repr(d) for d in get_user_owned_domains(user)):
		return f"(`tabMail Alias`.domain_name IN ({domains}))"
	else:
		return "1=0"
