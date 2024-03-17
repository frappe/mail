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
			self.update_virtual_mailbox(enabled=self.enabled)

	def on_trash(self) -> None:
		self.update_virtual_mailbox(enabled=False)

	def validate_email(self) -> None:
		email_domain = self.email.split("@")[1]

		if email_domain != self.domain_name:
			frappe.throw(
				_("Email domain {0} does not match with domain {1}.").format(
					frappe.bold(email_domain), frappe.bold(self.domain_name)
				)
			)

	def validate_domain(self) -> None:
		if frappe.session.user == "Administrator" or frappe.flags.ingore_domain_validation:
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

	def update_virtual_mailbox(self, enabled: bool | int) -> None:
		virtual_mailboxes = [{"mailbox": self.email, "enabled": 1 if enabled else 0}]
		update_virtual_mailboxes(virtual_mailboxes)


@frappe.whitelist()
def create_dmarc_mailbox(domain_name: str) -> "Mailbox":
	dmarc_email = f"dmarc@{domain_name}"
	frappe.flags.ingore_domain_validation = True
	return create_mailbox(domain_name, dmarc_email, "DMARC")


def create_mailbox(
	domain_name: str, user: str, display_name: Optional[str] = None
) -> "Mailbox":
	if not frappe.db.exists("Mailbox", user):
		if not frappe.db.exists("User", user):
			mailbox_user = frappe.new_doc("User")
			mailbox_user.email = user
			mailbox_user.first_name = display_name
			mailbox_user.user_type = "System User"
			mailbox_user.send_welcome_email = 0
			mailbox_user.add_roles("System Manager")  # TODO: Role Permissions
			mailbox_user.save(ignore_permissions=True)

		mailbox = frappe.new_doc("Mailbox")
		mailbox.domain_name = domain_name
		mailbox.user = user
		mailbox.display_name = display_name
		mailbox.save(ignore_permissions=True)

		return mailbox

	return frappe.get_doc("Mailbox", user)


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
