# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import Optional
from frappe.model.document import Document
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from mail.utils import (
	get_user_owned_domains,
	is_system_manager,
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

	def on_update(self) -> None:
		self.sync_mail_alias(enabled=self.enabled)

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

	def sync_mail_alias(self, enabled: bool | int) -> None:
		"""Updates the alias in the agents."""

		mailboxes = [m.mailbox for m in self.mailboxes]
		aliases = [
			{"alias": self.alias, "enabled": 1 if enabled else 0, "mailboxes": mailboxes}
		]
		sync_mail_aliases(aliases)


@frappe.whitelist()
def sync_mail_aliases(
	mail_aliases: Optional[list[dict]] = None, agents: Optional[str | list] = None
) -> None:
	"""Updates the aliases in the agents."""

	if not mail_aliases:
		mail_aliases = frappe.db.get_all(
			"Mail Alias",
			filters={"enabled": 1},
			fields=["name AS alias", "enabled"],
		)

		for alias in mail_aliases:
			alias["mailboxes"] = frappe.db.get_all(
				"Mail Alias Mailbox",
				filters={"parenttype": "Mail Alias", "parent": alias["alias"]},
				pluck="mailbox",
			)

	if mail_aliases:
		if not agents:
			agents = frappe.db.get_all(
				"Mail Agent", filters={"enabled": 1, "incoming": 1}, pluck="name"
			)
		elif isinstance(agents, str):
			agents = [agents]

		for agent in agents:
			create_agent_job(
				agent,
				"Sync Mail Aliases",
				request_data={"mail_aliases": mail_aliases},
			)


def has_permission(doc: "Document", ptype: str, user: str) -> bool:
	if doc.doctype != "Mail Alias":
		return False

	return is_system_manager(user) or (doc.domain_name in get_user_owned_domains(user))


def get_permission_query_condition(user: Optional[str]) -> str:
	if not user:
		user = frappe.session.user

	if is_system_manager(user):
		return ""

	if domains := ", ".join(repr(d) for d in get_user_owned_domains(user)):
		return f"(`tabMail Alias`.domain_name IN ({domains}))"
	else:
		return "1=0"
