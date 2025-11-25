import ipaddress
import os
import re
import socket

import frappe
from croniter import CroniterBadCronError, croniter
from frappe import _
from frappe.utils.caching import request_cache
from validate_email_address import validate_email

from mail.server.doctype.mail_principal_binding.mail_principal_binding import get_domain_tenant
from mail.utils.cache import get_account_for_user, get_tenant_for_domain, get_tenant_for_user
from mail.utils.user import has_role, is_administrator


def is_valid_host(host: str) -> bool:
	"""Returns True if the host is a valid hostname else False."""

	return bool(re.compile(r"^[a-zA-Z0-9_-]+$").match(host))


def is_valid_ip_address(ip_address: str, category: str | None = None) -> bool:
	"""Returns True if the IP address is valid else False."""

	try:
		ip_obj = ipaddress.ip_address(ip_address)

		if category:
			if category == "private":
				return ip_obj.is_private
			elif category == "public":
				return not ip_obj.is_private

		return True
	except ValueError:
		return False


def is_port_open(fqdn: str, port: int, timeout: int = 10) -> bool:
	"""Returns True if the port is open else False."""

	try:
		with socket.create_connection((fqdn, port), timeout=timeout):
			return True
	except (TimeoutError, OSError):
		return False


def is_subaddressed_email(email: str, raise_exception: bool = False) -> bool:
	"""Returns True if the email address contains subaddressing else False."""

	if re.search(r"[^@]+\+[^@]+@", email):
		if raise_exception:
			frappe.throw(_("Subaddressing is not allowed in the email address."))

		return True
	return False


def is_email_assigned(email: str, raise_exception: bool = False) -> bool:
	"""Returns True if the email is already assigned to Mail Account, Mailing List, or Mail Alias, else False."""

	if frappe.db.exists("Mail Principal Binding", {"principal_name": email}):
		if raise_exception:
			frappe.throw(_("The email address {0} is already assigned.").format(frappe.bold(email)))
		return True

	return False


def is_valid_email_for_domain(email: str, domain_name: str, raise_exception: bool = False) -> bool:
	"""Returns True if the email domain matches with the given domain else False."""

	email_domain = email.split("@")[1]

	if email_domain != domain_name:
		if raise_exception:
			frappe.throw(
				_("Email domain {0} does not match with domain {1}.").format(
					frappe.bold(email_domain), frappe.bold(domain_name)
				)
			)

		return False
	return True


def validate_email_address(
	email: str, check_mx: bool = True, verify: bool = True, smtp_timeout: int = 10
) -> bool:
	"""Validates the email address by checking MX records and RCPT TO."""

	return bool(validate_email(email=email, check_mx=check_mx, verify=verify, smtp_timeout=smtp_timeout))


@request_cache
def validate_domain_is_verified(domain_name: str) -> None:
	"""Validates if the domain is verified."""

	if not frappe.db.exists(
		"Mail Principal Binding",
		{"principal_name": domain_name, "principal_type": "Domain", "is_verified": 1},
	):
		frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(domain_name)))


@request_cache
def validate_domain_owned_by_tenant(domain_name: str, tenant: str) -> None:
	"""Validates if the domain is owned by the tenant."""

	if tenant != get_domain_tenant(domain_name, raise_exception=False):
		frappe.throw(_("Domain {0} is not owned by the tenant.").format(frappe.bold(domain_name)))


def is_valid_cron_expression(expression: str, raise_exception: bool = False) -> bool:
	"""Returns True if the expression is a valid Cron expression else False."""

	try:
		croniter(expression)
		return True
	except CroniterBadCronError:
		if raise_exception:
			frappe.throw(
				_("{0} is not a valid Cron expression.").format(f"<code>{expression}</code>"),
				title=_("Bad Cron Expression"),
			)
		return False


def validate_jmap_structure(base_dir: str, raise_exception: bool = False) -> list[str]:
	"""Validates a JMAP import directory. Returns a list of missing files or folders."""

	required_files = {
		"emails.json",
		"identities.json",
		"mailboxes.json",
		"sieve.json",
		"vacation.json",
	}
	required_dirs = {"blobs"}

	missing = []
	base_folder = os.path.basename(base_dir)

	for file in required_files:
		if not os.path.isfile(os.path.join(base_dir, file)):
			missing.append(f"/{base_folder}/{file}")

	for dir in required_dirs:
		if not os.path.isdir(os.path.join(base_dir, dir)):
			missing.append(f"/{base_folder}/{dir}/")

	if missing and raise_exception:
		frappe.throw(
			_("Missing required files/directories for JMAP format: {0}").format(
				", ".join(f"{m}" for m in missing)
			),
			title=_("Invalid JMAP Structure"),
		)

	return missing


def is_valid_maildir(base_dir: str, raise_exception: bool = False) -> bool:
	"""Checks if the given base directory is a valid Maildir."""

	required_dirs = ["cur", "new", "tmp"]
	result = all(os.path.isdir(os.path.join(base_dir, d)) for d in required_dirs)

	if not result and raise_exception:
		frappe.throw(
			_("Invalid Maildir format: missing {0} directories.").format(
				", ".join(f"<code>{d}</code>" for d in required_dirs)
			),
			title=_("Invalid Maildir"),
		)

	return result


def validate_maildir_or_maildirpp(base_dir: str, raise_exception: bool = False) -> list[str]:
	"""Validates a base Maildir or Maildir++ structure. Returns a list of invalid subdirs (relative paths)."""

	invalid_dirs = []

	def to_rel(path) -> str:
		rel = os.path.relpath(path, base_dir)
		return "/" if rel == "." else f"/{rel}"

	if not is_valid_maildir(base_dir, raise_exception=False):
		invalid_dirs.append("/")

	for entry in os.listdir(base_dir):
		full_path = os.path.join(base_dir, entry)
		if entry.startswith(".") and os.path.isdir(full_path):
			if not is_valid_maildir(full_path, raise_exception=False):
				invalid_dirs.append(to_rel(full_path))

	if invalid_dirs and raise_exception:
		frappe.throw(
			_("Invalid Maildir format in the following directories: {0}").format(
				", ".join(f"<code>{d}</code>" for d in invalid_dirs)
			),
			title=_("Invalid Maildir"),
		)

	return invalid_dirs


def validate_nested_maildir_tree(base_dir: str, raise_exception: bool = False) -> list[str]:
	"""Recursively validates a nested Maildir++ tree. Returns list of invalid directories (relative paths)."""

	invalid_dirs = []

	def to_rel(path) -> str:
		rel = os.path.relpath(path, base_dir)
		return "/" if rel == "." else f"/{rel}"

	def check_dir(path: str) -> None:
		if not is_valid_maildir(path, raise_exception=False):
			invalid_dirs.append(to_rel(path))

		for entry in os.listdir(path):
			full_path = os.path.join(path, entry)
			if entry.startswith(".") and os.path.isdir(full_path):
				check_dir(full_path)

	check_dir(base_dir)

	if invalid_dirs and raise_exception:
		frappe.throw(
			_("Invalid Maildir format in the following directories: {0}").format(
				", ".join(f"<code>{d}</code>" for d in invalid_dirs)
			),
			title=_("Invalid Maildir"),
		)

	return invalid_dirs


def has_permission_for_user(user: str, raise_exception: bool = True) -> bool:
	"""Checks if the current user has permission to access the given user."""

	current_user = frappe.session.user
	has_permission = user == current_user or is_administrator(current_user)

	if not has_permission and raise_exception:
		frappe.throw(_("You do not have permission to access this resource."), frappe.PermissionError)

	return has_permission
