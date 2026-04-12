# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	add_to_date,
	get_datetime,
	get_url,
	now,
	now_datetime,
	random_string,
	validate_email_address,
)

from mail.utils import generate_random_phrase, get_mail_config
from mail.utils.user import is_mail_admin, is_system_manager
from mail.utils.validation import (
	is_email_assigned,
	is_subaddressed_email,
	is_valid_email_for_domain,
	validate_domain_is_verified,
	validate_local_domain,
	validate_max_accounts,
)


class MailAccountRequest(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	@property
	def is_expired(self) -> bool:
		return self.expires_at and get_datetime(self.expires_at) < now_datetime()

	def before_insert(self) -> None:
		self.set_request_key()

	def validate(self) -> None:
		self.validate_email()

		if self.is_new():
			self.set_expires_at()
			self.set_ip_address()

			validate_max_accounts()

			self.validate_invited_by()
			self.validate_domain()
			self.validate_account()
			self.validate_roles()

	def after_insert(self) -> None:
		if self.send_invite:
			self.send_verification_email()

	def validate_email(self) -> None:
		"""Validates email if needed."""

		if not self.backup_email:
			frappe.throw(_("Backup Email is required."))

		self.backup_email = self.backup_email.strip().lower()
		validate_email_address(self.backup_email, throw=True)

	def set_expires_at(self) -> None:
		"""Sets the expiry date of the request."""

		if not self.expires_at:
			self.expires_at = add_to_date(now(), days=1)

	def set_ip_address(self) -> None:
		"""Sets the IP address of the request."""

		self.ip_address = frappe.local.request_ip

	def validate_invited_by(self) -> None:
		"""Validates the invited_by."""

		user = frappe.session.user

		if is_system_manager(user):
			if not self.invited_by:
				frappe.throw(_("Invited By is required"))
		else:
			self.invited_by = user

		if not is_mail_admin(self.invited_by):
			frappe.throw(_("User {0} does not have permission to invite.").format(self.invited_by))

	def validate_domain(self) -> None:
		"""Validates the domain."""

		if not self.domain_name:
			frappe.throw(_("Domain is mandatory."))

		validate_local_domain(self.domain_name)
		validate_domain_is_verified(self.domain_name)

	def validate_account(self) -> None:
		"""Validates the account."""

		self.account = self.account.strip().lower()
		validate_email_address(self.account, throw=True)
		is_subaddressed_email(self.account, raise_exception=True)
		is_email_assigned(self.account, raise_exception=True)

		if not is_valid_email_for_domain(self.account, self.domain_name):
			frappe.throw(
				_("Account domain {0} does not match with domain {1}.").format(
					frappe.bold(self.account.split("@")[1]), frappe.bold(self.domain_name)
				)
			)

		if frappe.db.exists("User", {"email": self.account}):
			frappe.throw(_("User {0} is already registered.").format(self.account))

	def validate_roles(self) -> None:
		"""Validates the roles."""

		roles = set([r.strip() for r in self.roles.split("\n")]) if self.roles else set()
		roles.add("User")
		self.roles = "\n".join(roles)

	def validate_expired(self) -> None:
		"""Forbids action if the request has expired."""

		if self.is_expired:
			frappe.throw(_("This request has expired. Please create a new one."))

	def set_request_key(self) -> None:
		"""Sets a random key for the request."""

		self.request_key = random_string(32)

	@frappe.whitelist()
	def send_verification_email(self) -> None:
		"""Send verification email to the user."""

		if not self.backup_email:
			frappe.throw(_("Email is required to send invite"))

		self.validate_expired()

		if self.invited_by:
			subject = _("You have been invited by {0} to join Frappe Mail").format(self.invited_by)
			template = "generic"
			args = {
				"title": _("You have been invited by {0} to join Frappe Mail.").format(self.invited_by),
				"description": _("Please confirm your email address by clicking the button below."),
				"button": _("Verify Account"),
				"link": get_url("/mail/signup/" + self.request_key),
			}

			frappe.sendmail(
				recipients=self.backup_email,
				subject=subject,
				template=template,
				args=args,
				now=True,
			)
			frappe.msgprint(_("Verification email sent successfully."), indicator="green", alert=True)

	@frappe.whitelist()
	def force_verify_and_create_account(self, first_name: str, last_name: str, password: str) -> None:
		"""Force verify and create account for invited user."""

		self.validate_expired()

		if self.is_verified:
			frappe.throw(_("Account is already verified and created."))

		user = frappe.session.user
		if not is_system_manager(user) and not is_mail_admin(user):
			frappe.throw(_("You are not authorized to perform this action."))

		self.db_set("is_verified", 1)
		self.create_account(first_name, last_name, password)

	def create_account(self, first_name: str, last_name: str, password: str) -> None:
		"""Create mail account for the user."""

		if not self.is_verified:
			frappe.throw(_("Please verify the email address first."))

		if frappe.db.exists("Principal Settings", {"principal_name": self.account}):
			frappe.throw(_("Account {0} is already created.").format(self.account))

		if not password:
			frappe.throw(_("Password is required to create account."))

		if frappe.db.exists("User", {"email": self.account}):
			frappe.throw(_("User with email {0} already exists.").format(frappe.bold(self.account)))

		roles = set([r.lower() for r in self.roles.split("\n")]) if self.roles else set(["user"])
		local_roles = ["Mail Admin"] if "admin" in roles or "tenant-admin" in roles else []

		# Create User
		user = create_user(self.account, first_name, last_name, password, local_roles)

		# Generate App Password
		app_password = generate_random_phrase()

		# Create Principal
		principal = frappe.new_doc("Principal")
		principal.type = "Individual"
		principal._name = self.account
		principal.description = f"{first_name} {last_name}"
		principal.password = password
		principal.user = user
		principal.append("app_passwords", {"identifier": frappe.local.site, "password": app_password})

		for role in roles:
			principal.append("roles", {"role": role})

		principal.insert(ignore_permissions=True)

		# Create User Settings
		user_settings = frappe.new_doc("User Settings")
		user_settings.user = user
		user_settings.server_url = get_mail_config().get("server_url")
		user_settings.username = self.account
		user_settings.app_password = app_password
		user_settings.backup_email = self.backup_email
		user_settings.save(ignore_permissions=True)

		# Create Push Subscription
		if frappe.utils.get_url().startswith("https"):
			ps = frappe.new_doc("Push Subscription")
			ps.user = user
			ps.insert(ignore_permissions=True)


def create_user(
	email: str,
	first_name: str,
	last_name: str | None = None,
	password: str | None = None,
	roles: list[str] | None = None,
) -> str:
	"""Creates a User document"""

	user = frappe.new_doc("User")
	user.first_name = first_name
	user.last_name = last_name
	user.username = email
	user.email = email
	user.owner = email
	user.send_welcome_email = 0
	if roles:
		user.append_roles(*roles)
	if password:
		user.new_password = password
	user.insert(ignore_permissions=True)

	return user.name


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Account Request":
		return False

	user = user or frappe.session.user

	if is_system_manager(user) or is_mail_admin(user):
		return True

	return False


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user) or is_mail_admin(user):
		return ""

	return "1=0"
