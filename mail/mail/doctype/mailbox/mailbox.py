# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import Optional
from pypika.terms import ExistsCriterion
from frappe.model.document import Document
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job


class Mailbox(Document):
	def validate(self) -> None:
		self.validate_email()
		self.validate_domain()
		self.validate_display_name()

	def on_update(self) -> None:
		previous = self.get_doc_before_save()

		if not previous or self.enabled != previous.get("enabled"):
			virtual_mailboxes = [{"mailbox": self.email, "enabled": self.enabled}]
			update_virtual_mailboxes(virtual_mailboxes)

	def on_trash(self) -> None:
		virtual_mailboxes = [{"mailbox": self.email, "enabled": 0}]
		update_virtual_mailboxes(virtual_mailboxes)

	def validate_email(self) -> None:
		email_domain = self.email.split("@")[1]

		if email_domain != self.domain_name:
			frappe.throw(
				_("Email domain {0} does not match with domain {1}.").format(
					frappe.bold(email_domain), frappe.bold(self.domain_name)
				)
			)

	def validate_domain(self) -> None:
		if frappe.session.user == "Administrator":
			return

		enabled, verified = frappe.db.get_value(
			"Mail Domain", self.domain_name, ["enabled", "verified"]
		)

		if not enabled:
			frappe.throw(_("Domain {0} is disabled.").format(frappe.bold(self.domain_name)))
		if not verified:
			frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(self.domain_name)))

	def validate_display_name(self) -> None:
		if self.is_new() and not self.display_name:
			self.display_name = frappe.db.get_value("User", self.user, "full_name")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_user(
	doctype: Optional[str] = None,
	txt: Optional[str] = None,
	searchfield: Optional[str] = None,
	start: Optional[int] = 0,
	page_len: Optional[int] = 20,
	filters: Optional[dict] = None,
) -> list:
	domain_name = filters.get("domain_name")

	if not domain_name:
		return []

	USER = frappe.qb.DocType("User")
	MAILBOX = frappe.qb.DocType("Mailbox")

	return (
		frappe.qb.from_(USER)
		.select(USER.name)
		.where(
			(USER.enabled == 1)
			& (USER[searchfield].like(f"%{txt}%"))
			& (USER.name.like(f"%@{domain_name}"))
			& ExistsCriterion(
				frappe.qb.from_(MAILBOX).select(MAILBOX.name).where(MAILBOX.name == USER.name)
			).negate()
		)
		.limit(page_len)
	).run(as_dict=False)


@frappe.whitelist()
def update_virtual_mailboxes(
	virtual_mailboxes: Optional[list[dict]] = None, servers: Optional[str | list] = None
) -> None:
	if not virtual_mailboxes:
		virtual_mailboxes = frappe.db.get_all(
			"Mailbox", {"enabled": 1}, ["name AS mailbox", "enabled"]
		)

	if virtual_mailboxes:
		if not servers:
			servers = frappe.db.get_all(
				"Mail Server", {"enabled": 1, "incoming": 1}, pluck="name"
			)
		elif isinstance(servers, str):
			servers = [servers]

		for server in servers:
			create_agent_job(
				server,
				"Update Virtual Mailboxes",
				request_data={"virtual_mailboxes": virtual_mailboxes},
			)
