import frappe
from frappe.core.api.file import create_new_folder

from mail.mail.doctype.rate_limit.rate_limit import create_rate_limit
from mail.stalwart.cli import StalwartCLI


def after_install() -> None:
	create_mail_admin_role()
	add_rate_limits()
	create_new_folder("Frappe Mail", "Home")
	generate_jmap_push_keys()


def create_mail_admin_role() -> None:
	"""Create the Mail Admin role if missing.

	Deliberately NOT shipped as a fixture: fixture sync deletes and re-inserts the role
	on every `bench migrate`, and the fresh insert makes Frappe's Role.on_update see
	desk_access as "changed". That re-evaluates user_type for every holder and clears the
	sessions of any whose type flips — logging mail users out on every migrate.
	"""

	if not frappe.db.exists("Role", "Mail Admin"):
		frappe.get_doc({"doctype": "Role", "role_name": "Mail Admin", "desk_access": 0}).insert(
			ignore_permissions=True
		)


def after_migrate() -> None:
	StalwartCLI()._install()


def add_rate_limits() -> None:
	"""Add rate limits."""

	rate_limits = [
		# mail.api.account
		{"method_path": "mail.api.account.signup", "limit": 5, "seconds": 60 * 60},
		{"method_path": "mail.api.account.resend_otp", "limit": 5, "seconds": 60 * 60},
		{"method_path": "mail.api.account.verify_otp", "limit": 5, "seconds": 60 * 60},
		{"method_path": "mail.api.account.get_account_request", "limit": 5, "seconds": 60 * 60},
		{"method_path": "mail.api.account.create_account", "limit": 10, "seconds": 60 * 60},
		{"method_path": "mail.api.account.send_reset_password_link", "limit": 5, "seconds": 60 * 60},
		{"method_path": "mail.api.account.validate_email_assigned", "limit": 10, "seconds": 60 * 60},
		# mail.api.admin
		{"method_path": "mail.api.admin.add_domain", "limit": 10, "seconds": 24 * 60 * 60},
		{"method_path": "mail.api.admin.add_member", "limit": 10, "seconds": 60 * 60},
		# mail.api.inbound
		{"method_path": "mail.api.inbound.fetch_blob", "limit": 60, "seconds": 60},
		{"method_path": "mail.api.inbound.pull", "limit": 10, "seconds": 60},
		{"method_path": "mail.api.inbound.pull_raw", "limit": 10, "seconds": 60},
		# mail.api.outbound
		{"method_path": "mail.api.outbound.upload_attachment", "limit": 60, "seconds": 60},
		{"method_path": "mail.api.outbound.send", "limit": 300, "seconds": 60},
		{"method_path": "mail.api.outbound.send_raw", "limit": 300, "seconds": 120},
		# mail.api.spamd
		{"method_path": "mail.api.spamd.scan", "limit": 60, "seconds": 60},
		{"method_path": "mail.api.spamd.get_spam_score", "limit": 60, "seconds": 60},
	]

	for rl in rate_limits:
		create_rate_limit(**rl)


def generate_jmap_push_keys() -> None:
	"""Generates new JMAP push subscription encryption keys and saves them in Mail Settings."""

	settings = frappe.get_single("Mail Settings")
	if not settings.jmap_push_p256dh or not settings.jmap_push_private_key or not settings.jmap_push_auth:
		settings._generate_jmap_push_keys()
