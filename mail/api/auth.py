import frappe
from frappe import _

from mail.utils.cache import get_user_emails
from mail.utils.user import has_role, is_jmap_configured, is_system_manager


def check_app_permission() -> bool:
	"""Returns True if the user has permission to access the app."""

	user = frappe.session.user
	return is_jmap_configured(user) or is_system_manager(user)


@frappe.whitelist(methods=["POST"])
def validate(email: str) -> None:
	"""Validates if the user is allowed to send or receive emails."""

	validate_user()
	validate_email_ownership(email)


def validate_user() -> None:
	"""Validates if the user is allowed to send or receive emails."""

	user = frappe.session.user

	if not is_jmap_configured(user):
		frappe.throw(
			_("User {0} does not have JMAP settings configured.").format(frappe.bold(user)),
			frappe.PermissionError,
		)


def validate_email_ownership(email: str) -> None:
	"""Validates if the email address is associated with the user."""

	user = frappe.session.user
	if email.lower() not in get_user_emails(user):
		frappe.throw(
			_("Email address {0} is not associated with the user {1}.").format(
				frappe.bold(email), frappe.bold(user)
			)
		)
