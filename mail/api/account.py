import json
from typing import Literal

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, get_url, now_datetime
from frappe.utils.data import sha256_hash

from mail.api.admin import add_member
from mail.api.mail import normalize_filter
from mail.client.doctype.identity.identity import fetch_identities
from mail.server.doctype.mail_account_request.mail_account_request import create_user
from mail.utils import convert_html_to_text, user_context
from mail.utils.cache import get_signup_domains
from mail.utils.rate_limiter import dynamic_rate_limit
from mail.utils.user import get_tenant_for_domain, get_user_tenant, has_user_settings
from mail.utils.validation import is_email_assigned


@frappe.whitelist(allow_guest=True)
@dynamic_rate_limit()
def validate_email_assigned(email: str) -> None:
	"""Checks if email is already assigned"""

	if is_email_assigned(email):
		frappe.throw(_("Username already taken."))


@frappe.whitelist(allow_guest=True)
@dynamic_rate_limit()
def signup(
	username: str,
	domain: str,
	email: str,
	password: str,
	first_name: str,
	last_name: str | None = None,
) -> None:
	"""Create a new Mail Account for signup"""

	if not frappe.db.get_single_value("Mail Settings", "allow_signup"):
		frappe.throw(_("Signup is disabled."))

	if domain not in get_signup_domains():
		frappe.throw(_("Domain {0} is not allowed for signup.").format(domain))

	with user_context("Administrator"):
		tenant = get_tenant_for_domain(domain)
		add_member(tenant, username, domain, "Mail User", False, email, first_name, last_name, password)


@frappe.whitelist(allow_guest=True)
@dynamic_rate_limit()
def resend_otp(account_request: str) -> None:
	"""Resend OTP to the user"""

	account_request = frappe.get_doc("Mail Account Request", account_request)
	account_request.set_otp()
	account_request.save(ignore_permissions=True)
	account_request.send_verification_email()


@frappe.whitelist(allow_guest=True)
@dynamic_rate_limit()
def verify_otp(account_request: str, otp: str) -> str:
	"""Verify the OTP and return the request key"""

	otp_hash = frappe.cache.get_value(f"account_request_otp_hash:{account_request}", expires=True)
	if not otp_hash or otp_hash != frappe.utils.sha256_hash(otp):
		frappe.throw(_("Invalid OTP. Please try again."))

	frappe.cache.delete_value(f"account_request_otp_hash:{account_request}")
	return frappe.db.get_value("Mail Account Request", account_request, "request_key")


@frappe.whitelist(allow_guest=True)
@dynamic_rate_limit()
def get_account_request(request_key: str) -> dict | None:
	"""Return the account request details"""

	if account_request := frappe.db.get_value(
		"Mail Account Request",
		{"request_key": request_key},
		["backup_email", "is_verified", "expires_at", "account"],
		as_dict=True,
	):
		is_expired = 0
		if expires_at := account_request["expires_at"]:
			is_expired = cint(get_datetime(expires_at) < now_datetime())
		account_request.pop("expires_at")
		account_request["is_expired"] = is_expired
		return account_request


@frappe.whitelist(allow_guest=True)
@dynamic_rate_limit()
def create_account(request_key: str, first_name: str, last_name: str, password: str) -> None:
	"""Create a new user account"""

	account_request = frappe.get_last_doc("Mail Account Request", {"request_key": request_key})
	account_request.validate_expired()
	account_request.is_verified = 1
	account_request.save(ignore_permissions=True)

	if account_request.account:
		account_request.create_account(first_name, last_name, password)
	else:
		create_user(account_request.backup_email, first_name, last_name, password, ["Mail Admin"])


@frappe.whitelist(allow_guest=True)
def get_user_info() -> dict | None:
	"""Returns user information."""

	user = frappe.session.user
	if user == "Guest":
		return None

	if not has_user_settings(user):
		user_settings = frappe.new_doc("User Settings")
		user_settings.user = user
		user_settings.insert(ignore_permissions=True)

	USER = frappe.qb.DocType("User")
	USER_SETTINGS = frappe.qb.DocType("User Settings")

	result = (
		frappe.qb.from_(USER)
		.join(USER_SETTINGS)
		.on(USER.name == USER_SETTINGS.user)
		.select(
			USER.name,
			USER.email,
			USER.enabled,
			USER.user_image,
			USER.full_name,
			USER.first_name,
			USER.last_name,
			USER.user_type,
			USER.username,
			USER.api_key,
			USER_SETTINGS.default_outgoing_email,
			USER_SETTINGS.color_scheme,
			USER_SETTINGS.group_messages_by,
			USER_SETTINGS.show_reading_pane,
			USER_SETTINGS.name.as_("user_settings"),
		)
		.where(USER.name == user)
	).run(as_dict=True)

	if not result:
		return None

	data = result[0]

	user_roles = frappe.get_roles(user)
	data.tenant = get_user_tenant()
	data.is_mail_user = "Mail User" in user_roles and user != "Administrator"
	data.is_mail_admin = "Mail Admin" in user_roles
	data.is_system_manager = "System Manager" in user_roles or user == "Administrator"

	if data.tenant:
		data.tenant_name, tenant_owner = frappe.db.get_value(
			"Mail Tenant", data.tenant, ["tenant_name", "user"]
		)
		data.is_tenant_owner = tenant_owner == user

	return data


def get_backup_email(user: str) -> str:
	"""Return backup email for a user or the user's email if backup doesn't exist"""

	if backup_email := frappe.db.get_value("User Settings", {"user": user}, "backup_email"):
		return backup_email

	if frappe.db.exists("User", user):
		return frappe.db.get_value("User", user, "email")

	frappe.throw(_("User {0} does not exist.").format(frappe.bold(user)))


def set_reset_password_key(email: str) -> str:
	"""Generate and store a reset password key for a user"""

	key = frappe.generate_hash()
	hashed_key = sha256_hash(key)
	frappe.db.set_value(
		"User",
		email,
		{"reset_password_key": hashed_key, "last_reset_password_key_generated_on": now_datetime()},
	)
	return key


def censor_email(email: str) -> str:
	"""Censor the email address to protect privacy"""

	username, domain = email.split("@")
	censored_username = username[0] + "*" * (len(username) - 1)
	return f"{censored_username}@{domain}"


@frappe.whitelist(allow_guest=True)
@dynamic_rate_limit()
def send_reset_password_link(user: str) -> str:
	"""Send reset password link to the user"""

	email = get_backup_email(user)
	key = set_reset_password_key(user)

	frappe.sendmail(
		recipients=email,
		subject=_("Reset Password"),
		template="reset_password",
		args={"link": get_url("/mail/reset-password/" + key)},
		now=True,
	)

	if email == user:
		return email

	return censor_email(email)


@frappe.whitelist(allow_guest=True)
def get_user_for_reset_password_key(key: str) -> str:
	"""Return the user for a reset password key"""

	hashed_key = sha256_hash(key)
	return frappe.db.get_value("User", {"reset_password_key": hashed_key}, "name")


@frappe.whitelist()
def create_mail_import(
	format: Literal["eml", "jmap", "mbox", "maildir", "maildir-nested"],
	file: str,
	mailbox: str | None = None,
	seen: bool = False,
) -> None:
	"""Creates mail exchange of operation import"""

	doc = frappe.new_doc("Mail Exchange")
	doc.user = frappe.session.user
	doc.operation = "Import"
	doc.import_format = format
	doc.import_file = file
	if format in ["eml", "maildir"] and mailbox:
		doc.import_metadata = json.dumps({"mailboxIds": {mailbox: True}, "keywords": {"$seen": seen}})
	doc.insert()
	doc.submit()


@frappe.whitelist()
def create_mail_export(
	format: Literal["jmap", "mbox", "maildir", "maildir-nested"],
	archive_type: Literal[".zip", ".tgz", ".tar.gz"],
	sort: Literal["Received At (ASC)", "Received At (DESC)"],
	limit: int | None = None,
	filter: dict | None = None,
) -> None:
	"""Creates mail exchange of operation export"""

	doc = frappe.new_doc("Mail Exchange")
	doc.user = frappe.session.user
	doc.operation = "Export"
	doc.export_format = format
	doc.export_archive_type = archive_type
	doc.export_sort = sort
	doc.export_limit = limit
	if filter:
		filter = {k: v for k, v in filter.items() if v}
		if filter:
			doc.export_filter = json.dumps(normalize_filter(filter))
	doc.insert()
	doc.submit()


@frappe.whitelist()
def is_push_notification_relay_enabled() -> bool:
	return frappe.db.get_single_value("Push Notification Settings", "enable_push_notification_relay")


@frappe.whitelist()
def get_quota() -> dict:
	"""Return quota usage for the user"""

	result = {
		"disk_quota": 0,
		"used_quota": 0,
		"used_percentage": 0,
	}

	for quota in frappe.db.get_all("Quota", {"user": frappe.session.user}):
		if scope := quota["scope"]:
			if scope == "account":
				result["disk_quota"] = quota["hard_limit"]
				result["used_quota"] = quota["used"]

				if result["disk_quota"] > 0:
					result["used_percentage"] = (result["used_quota"] / result["disk_quota"]) * 100

				break

	return result


@frappe.whitelist()
def get_identities() -> list[dict]:
	"""Return the email identities for the user"""

	return fetch_identities(frappe.session.user, page=1, limit=100)


@frappe.whitelist()
def set_signature(identity: str, signature: str) -> None:
	doc = frappe.get_doc("Identity", identity)
	doc.html_signature = signature
	doc.text_signature = convert_html_to_text(signature)
	doc.db_update()
