import frappe
from frappe import _
from typing import Optional
from mail.utils.user import has_role, is_mailbox_owner
from mail.utils.validation import (
	validate_mailbox_for_incoming,
	validate_mailbox_for_outgoing,
)


@frappe.whitelist(methods=["POST"])
def validate(
	mailbox: Optional[str] = None, for_inbound: bool = False, for_outbound: bool = False
) -> None:
	"""Validates the mailbox for inbound and outbound emails."""

	if mailbox:
		user = frappe.session.user

		if not has_role(user, "Mailbox User"):
			frappe.throw(
				_("User {0} is not allowed to access mailboxes.").format(frappe.bold(user))
			)

		if not is_mailbox_owner(mailbox, user):
			frappe.throw(
				_("Mailbox {0} is not associated with user {1}").format(
					frappe.bold(mailbox), frappe.bold(user)
				)
			)

		if for_inbound:
			validate_mailbox_for_incoming(mailbox)

		if for_outbound:
			validate_mailbox_for_outgoing(mailbox)
