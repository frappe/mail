# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


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

from mail.utils import generate_random_phrase
from mail.utils.cache import get_cluster_for_tenant, get_tenant_for_user
from mail.utils.user import has_role, is_system_manager, is_tenant_admin
from mail.utils.validation import (
	is_email_assigned,
	is_subaddressed_email,
	is_valid_email_for_domain,
	validate_domain_is_verified,
	validate_domain_owned_by_tenant,
	validate_max_accounts,
)


class MailAccountRequest(Document):
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

			validate_max_accounts(self.tenant)

			self.validate_invited_by_and_tenant()
			self.validate_domain()
			self.validate_account()

	def after_insert(self) -> None:
		if self.send_invite:
			self.send_verification_email()

	def validate_email(self) -> None:
		"""Validates email if needed."""

		if not self.email:
			frappe.throw(_("Backup Email is required."))

		self.email = self.email.strip().lower()
		validate_email_address(self.email, throw=True)

	def set_expires_at(self) -> None:
		"""Sets the expiry date of the request."""

		if not self.expires_at:
			self.expires_at = add_to_date(now(), days=1)

	def set_ip_address(self) -> None:
		"""Sets the IP address of the request."""

		self.ip_address = frappe.local.request_ip

	def validate_invited_by_and_tenant(self) -> None:
		"""Validates the invited_by and tenant fields."""

		user = frappe.session.user
		if is_system_manager(user):
			if not self.invited_by:
				frappe.throw(_("Invited By is required"))
			elif not self.tenant:
				frappe.throw(_("Tenant is required"))
		else:
			self.invited_by = user
			self.tenant = get_tenant_for_user(user)

		if not is_tenant_admin(self.tenant, self.invited_by):
			frappe.throw(
				_("User {0} is not authorized to invite users to the tenant.").format(
					frappe.bold(self.invited_by)
				)
			)

	def validate_domain(self) -> None:
		"""Validates the domain."""

		if not self.domain_name:
			frappe.throw(_("Domain is mandatory."))

		validate_domain_owned_by_tenant(self.domain_name, self.tenant)
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

		if not self.email:
			frappe.throw(_("Email is required to send invite"))

		self.validate_expired()

		if self.invited_by:
			subject = _("You have been invited by {0} to join Frappe Mail").format(self.invited_by)
			template = "generic"
			tenant_name = frappe.db.get_value("Mail Tenant", self.tenant, "tenant_name")
			args = {
				"title": _('You have been invited by {0} to join tenant "{1}" on Frappe Mail.').format(
					self.invited_by, tenant_name
				),
				"description": _("Please confirm your email address by clicking the button below."),
				"button": _("Verify Account"),
				"link": get_url("/mail/signup/" + self.request_key),
			}

			frappe.sendmail(
				recipients=self.email,
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
		if not is_system_manager(user) and not is_tenant_admin(self.tenant, user):
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

		roles = ["Mail User"]
		if self.is_admin:
			roles.append("Mail Admin")

		# Create User
		user = create_user(self.account, first_name, last_name, password, roles)
		_add_user_to_tenant(self.tenant, user, self.is_admin)

		# Generate App Password
		app_password = generate_random_phrase()

		# Create Principal
		principal = frappe.new_doc("Principal")
		principal.tenant = self.tenant
		principal.type = "Individual"
		principal._name = self.account
		principal.description = f"{first_name} {last_name}"
		principal.password = password
		principal.user = user
		principal.append("app_passwords", {"identifier": frappe.local.site, "password": app_password})
		principal.insert(ignore_permissions=True)

		# Create User Settings
		user_settings = frappe.new_doc("User Settings")
		user_settings.user = user
		user_settings.server_url = frappe.db.get_value(
			"Mail Cluster", get_cluster_for_tenant(self.tenant), "base_url"
		)
		user_settings.username = self.account
		user_settings.app_password = app_password
		user_settings.backup_email = self.email
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


def _add_user_to_tenant(tenant: str, user: str, is_admin: bool) -> None:
	"""Adds a User to a Tenant"""

	tenant = frappe.get_doc("Mail Tenant", tenant)
	tenant.add_member(user, is_admin)


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Account Request":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True

	if is_tenant_admin(doc.tenant, user):
		return True

	return False


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	if has_role(user, "Mail Admin"):
		if tenant := get_tenant_for_user(user):
			return f"(`tabMail Account Request`.`tenant` = {frappe.db.escape(tenant)})"

	return "1=0"
