import frappe
from frappe import _

from mail.utils.rate_limiter import dynamic_rate_limit
from mail.utils.user import (
	get_account_emails,
	get_user_personal_account,
	is_jmap_configured,
	is_system_manager,
)


def check_app_permission() -> bool:
	"""Returns True if the user has permission to access the app else False."""

	user = frappe.session.user
	return is_jmap_configured(user) or is_system_manager(user)


@frappe.whitelist(methods=["POST"])
@dynamic_rate_limit()
def validate(email: str) -> None:
	"""Validates if the email is associated with the user."""

	validate_user()
	validate_email_ownership(email)


def validate_user() -> None:
	"""Validates if the user has permission to access the app."""

	is_jmap_configured(frappe.session.user, raise_exception=True)


def validate_email_ownership(email: str) -> None:
	"""Validates if the email is associated with any account of the user."""

	email = email.strip().lower()
	if not email:
		frappe.throw(_("Email address is required."), frappe.MandatoryError)

	user = frappe.session.user
	account = get_user_personal_account(user, raise_exception=True)

	if email not in get_account_emails(account):
		frappe.throw(
			_("Email address '{0}' is not associated with any account of the user '{1}'.").format(
				email, user
			),
			frappe.PermissionError,
		)
