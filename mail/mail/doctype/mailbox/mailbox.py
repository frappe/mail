# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import Optional
from pypika.terms import ExistsCriterion
from frappe.model.document import Document
from mail.utils import validate_active_domain, is_valid_email_for_domain
from mail.mail.doctype.mail_agent_job.mail_agent_job import create_agent_job


class Mailbox(Document):
	def validate(self) -> None:
		self.validate_email()
		self.validate_domain()
		self.validate_display_name()

	def on_update(self) -> None:
		previous = self.get_doc_before_save()
		enabled = self.enabled and self.incoming

		if (
			not previous
			or self.enabled != previous.get("enabled")
			or self.incoming != previous.get("incoming")
		):
			if not enabled:
				self.validate_against_mail_alias()
			self.sync_mailbox(enabled=enabled)

	def on_trash(self) -> None:
		self.sync_mailbox(enabled=False)

	def validate_email(self) -> None:
		"""Validates the email address."""

		is_valid_email_for_domain(self.email, self.domain_name, raise_exception=True)

	def validate_domain(self) -> None:
		"""Validates the domain."""

		validate_active_domain(self.domain_name)

	def validate_display_name(self) -> None:
		"""Validates the display name."""

		if self.is_new() and not self.display_name:
			self.display_name = frappe.db.get_value("User", self.user, "full_name")

	def validate_against_mail_alias(self) -> None:
		"""Validates if the mailbox is linked with an active Mail Alias."""

		MA = frappe.qb.DocType("Mail Alias")
		MAM = frappe.qb.DocType("Mail Alias Mailbox")

		data = (
			frappe.qb.from_(MA)
			.left_join(MAM)
			.on(MA.name == MAM.parent)
			.select(MA.name)
			.where((MA.enabled == 1) & (MAM.mailbox == self.email))
			.limit(1)
		).run(pluck="name")

		if data:
			frappe.throw(
				_("Mailbox {0} is linked with active Mail Alias {1}.").format(
					frappe.bold(self.name), frappe.bold(data[0])
				)
			)

	def sync_mailbox(self, enabled: bool | int) -> None:
		"""Updates the mailbox in the agents."""

		mailboxes = [{"mailbox": self.email, "enabled": 1 if enabled else 0}]
		sync_mailboxes(mailboxes)


@frappe.whitelist()
def create_dmarc_mailbox(domain_name: str) -> "Mailbox":
	"""Creates a DMARC mailbox for the domain."""

	dmarc_email = f"dmarc@{domain_name}"
	frappe.flags.ingore_domain_validation = True
	return create_mailbox(domain_name, dmarc_email, outgoing=False, display_name="DMARC")


def create_mailbox(
	domain_name: str,
	user: str,
	incoming: bool = True,
	outgoing: bool = True,
	display_name: Optional[str] = None,
) -> "Mailbox":
	"""Creates a user and mailbox if not exists."""

	if not frappe.db.exists("Mailbox", user):
		if not frappe.db.exists("User", user):
			mailbox_user = frappe.new_doc("User")
			mailbox_user.email = user
			mailbox_user.username = user
			mailbox_user.first_name = display_name
			mailbox_user.user_type = "System User"
			mailbox_user.send_welcome_email = 0
			mailbox_user.add_roles("System Manager")  # TODO: Role Permissions
			mailbox_user.insert(ignore_permissions=True)

		mailbox = frappe.new_doc("Mailbox")
		mailbox.domain_name = domain_name
		mailbox.incoming = incoming
		mailbox.outgoing = outgoing
		mailbox.user = user
		mailbox.display_name = display_name
		mailbox.insert(ignore_permissions=True)

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
	"""Returns the users for the domain."""

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
def sync_mailboxes(
	mailboxes: Optional[list[dict]] = None, agents: Optional[str | list] = None
) -> None:
	"""Updates the mailboxes in the agents."""

	if not mailboxes:
		mailboxes = frappe.db.get_all(
			"Mailbox",
			filters={
				"enabled": 1,
				"incoming": 1,
			},
			fields=["name AS mailbox", "enabled"],
		)

	if mailboxes:
		if not agents:
			agents = frappe.db.get_all(
				"Mail Agent", filters={"enabled": 1, "incoming": 1}, pluck="name"
			)
		elif isinstance(agents, str):
			agents = [agents]

		for agent in agents:
			create_agent_job(
				agent,
				"Sync Mailboxes",
				request_data={"mailboxes": mailboxes},
			)
