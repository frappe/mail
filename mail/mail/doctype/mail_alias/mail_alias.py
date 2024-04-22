# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import Optional
from frappe.model.document import Document
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job
from mail.utils import (
	validate_active_domain,
	is_valid_email_for_domain,
	validate_mailbox_for_incoming,
)


class MailAlias(Document):
	def validate(self) -> None:
		self.validate_email()
		self.validate_domain()
		self.validate_mailboxes()

	def on_update(self) -> None:
		self.update_virtual_alias(enabled=self.enabled)

	def validate_email(self) -> None:
		is_valid_email_for_domain(self.alias, self.domain_name, raise_exception=True)

	def validate_domain(self) -> None:
		validate_active_domain(self.domain_name)

	def validate_mailboxes(self) -> None:
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

	def update_virtual_alias(self, enabled: bool | int) -> None:
		mailboxes = [m.mailbox for m in self.mailboxes]
		virtual_aliases = [
			{"alias": self.alias, "enabled": 1 if enabled else 0, "mailboxes": mailboxes}
		]
		update_virtual_aliases(virtual_aliases)


@frappe.whitelist()
def update_virtual_aliases(
	virtual_aliases: Optional[list[dict]] = None, agents: Optional[str | list] = None
) -> None:
	if not virtual_aliases:
		virtual_aliases = frappe.db.get_all(
			"Mail Alias",
			filters={"enabled": 1},
			fields=["name AS alias", "enabled"],
		)

		for alias in virtual_aliases:
			alias["mailboxes"] = frappe.db.get_all(
				"Mail Alias Mailbox",
				filters={"parenttype": "Mail Alias", "parent": alias["alias"]},
				pluck="mailbox",
			)

	if virtual_aliases:
		if not agents:
			agents = frappe.db.get_all(
				"Mail Agent", filters={"enabled": 1, "incoming": 1}, pluck="name"
			)
		elif isinstance(agents, str):
			agents = [agents]

		for agent in agents:
			create_agent_job(
				agent,
				"Update Virtual Aliases",
				request_data={"virtual_aliases": virtual_aliases},
			)
