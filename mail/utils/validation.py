import fnmatch
import ipaddress
import os
import re
import socket

import frappe
from croniter import CroniterBadCronError, croniter
from frappe import _
from frappe.utils.caching import request_cache
from validate_email_address import validate_email

from mail.utils.user import (
	get_cluster_for_tenant,
	get_principal_tenant,
	get_tenant_groups,
	get_tenant_mailing_lists,
	is_administrator,
	is_system_manager,
	is_tenant_admin,
	is_tenant_bound_user,
)


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
	"""Returns True if the email address is already assigned else False."""

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

	if not frappe.db.exists("Mail Principal Binding", {"principal_name": domain_name, "is_verified": 1}):
		frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(domain_name)))


@request_cache
def validate_domain_owned_by_tenant(domain_name: str, tenant: str) -> None:
	"""Validates if the domain is owned by the tenant."""

	if tenant != get_principal_tenant(domain_name, raise_exception=False):
		frappe.throw(_("Domain {0} is not owned by the tenant.").format(frappe.bold(domain_name)))


def validate_max_domains(tenant: str) -> None:
	"""Validates if the tenant has reached the maximum limit of domains."""

	max_domains = frappe.db.get_value("Mail Tenant", tenant, "max_domains")
	total_domains = frappe.db.count("Mail Principal Binding", {"tenant": tenant, "principal_type": "Domain"})

	if total_domains >= max_domains:
		frappe.throw(
			_("You have reached the maximum limit of {0} domains for the tenant.").format(
				frappe.bold(max_domains)
			)
		)


def validate_max_groups(tenant: str) -> None:
	"""Validates if the tenant has reached the maximum limit of groups."""

	max_groups = frappe.db.get_value("Mail Tenant", tenant, "max_groups")
	total_groups = frappe.db.count("Mail Principal Binding", {"tenant": tenant, "principal_type": "Group"})

	if total_groups >= max_groups:
		frappe.throw(
			_("You have reached the maximum limit of {0} groups for the tenant.").format(
				frappe.bold(max_groups)
			)
		)


def validate_max_accounts(tenant: str) -> None:
	"""Validates if the tenant has reached the maximum limit of mail accounts."""

	max_accounts = frappe.db.get_value("Mail Tenant", tenant, "max_accounts")
	total_accounts = frappe.db.count(
		"Mail Principal Binding", {"tenant": tenant, "principal_type": "Individual"}
	)

	if total_accounts >= max_accounts:
		frappe.throw(
			_("You have reached the maximum limit of {0} accounts for the tenant.").format(
				frappe.bold(max_accounts)
			)
		)


def validate_max_lists(tenant: str) -> None:
	"""Validates if the tenant has reached the maximum limit of lists."""

	max_lists = frappe.db.get_value("Mail Tenant", tenant, "max_mailing_lists")
	total_lists = frappe.db.count("Mail Principal Binding", {"tenant": tenant, "principal_type": "List"})

	if total_lists >= max_lists:
		frappe.throw(
			_("You have reached the maximum limit of {0} lists for the tenant.").format(
				frappe.bold(max_lists)
			)
		)


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


def validate_jmap_structure(
	base_dir: str, required_files: list[str], raise_exception: bool = False
) -> list[str]:
	"""Validates a JMAP import directory. Returns a list of missing files or folders."""

	required_files = required_files or {
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
	"""
	Checks if the given base directory is a valid Maildir.

	Valid if at least one of `cur`, `new`, or `tmp` exists
	and contains at least one file (recursively).
	"""

	def has_file(dir_path: str) -> bool:
		for _root, _dirs, files in os.walk(dir_path):
			if files:
				return True
		return False

	maildir_dirs = ("cur", "new", "tmp")
	for d in maildir_dirs:
		dir_path = os.path.join(base_dir, d)
		if os.path.isdir(dir_path) and has_file(dir_path):
			return True

	if raise_exception:
		frappe.throw(
			_("Invalid Maildir format: at least one of {0} must exist and contain files.").format(
				", ".join(f"<code>{d}</code>" for d in maildir_dirs)
			),
			title=_("Invalid Maildir"),
		)

	return False


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
	"""
	Recursively validates a nested Maildir++ tree.

	A mailbox is valid if it:
	- contains cur/ or new/
	- OR contains child mailboxes (.Child)
	"""

	invalid_dirs: list[str] = []
	base_dir = os.path.abspath(base_dir)

	def to_rel(path: str) -> str:
		rel = os.path.relpath(path, base_dir)
		return "/" if rel == "." else f"/{rel}"

	def is_valid_nested_mailbox(path: str) -> bool:
		try:
			entries = os.listdir(path)
		except OSError:
			return False

		has_maildir = any(
			name in ("cur", "new") and os.path.isdir(os.path.join(path, name)) for name in entries
		)
		has_children = any(
			name.startswith(".") and os.path.isdir(os.path.join(path, name)) for name in entries
		)

		return has_maildir or has_children

	def walk(path: str) -> None:
		for entry in os.listdir(path):
			if not entry.startswith("."):
				continue

			full_path = os.path.join(path, entry)
			if not os.path.isdir(full_path):
				continue

			if not is_valid_nested_mailbox(full_path):
				invalid_dirs.append(to_rel(full_path))

			walk(full_path)

	walk(base_dir)

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


def ensure_tenant_bound_user(user: str) -> None:
	"""Raises an exception if the user is not a tenant bound user."""

	if not is_tenant_bound_user(user):
		frappe.throw(
			_("User {0} is not a tenant bound user").format(user),
			frappe.PermissionError,
		)


def ensure_access_to_tenant(tenant: str) -> None:
	"""Ensures that the current user has access to the tenant."""

	user = frappe.session.user
	if tenant:
		if not is_tenant_admin(tenant, user) and not is_system_manager(user):
			frappe.throw(_("You do not permission to access Tenant {0}.").format(tenant))
	else:
		frappe.throw(_("Tenant not specified."))


def ensure_tenant_has_cluster(tenant: str) -> None:
	"""Ensures that the tenant is assigned to a mail cluster."""

	if not get_cluster_for_tenant(tenant):
		frappe.throw(_("Tenant {0} is not assigned to any cluster.").format(frappe.bold(tenant)))


def ensure_principal_belong_to_tenant(tenant: str, principal_name: str, raise_exception: bool = True) -> bool:
	"""Ensure that the principal belongs to the given tenant."""

	if not frappe.db.exists("Mail Principal Binding", {"tenant": tenant, "principal_name": principal_name}):
		if raise_exception:
			frappe.throw(
				_("Principal {0} does not belong to tenant {1}.").format(
					frappe.bold(principal_name), frappe.bold(tenant)
				)
			)
		return False

	return True


def ensure_emails_belong_to_tenant_domains(tenant: str, emails: list[str]) -> None:
	"""Ensure that the email domains belong to the given tenant."""

	domains = frappe.db.get_all(
		"Mail Principal Binding",
		filters={"tenant": tenant, "principal_type": "Domain", "is_verified": 1},
		pluck="principal_name",
	)
	tenant_name = frappe.db.get_value("Mail Tenant", tenant, "tenant_name")

	for email in emails:
		_user, domain = email.split("@", 1)
		if domain not in domains:
			frappe.throw(
				_("Email domain {0} is not associated with tenant {1} or is not verified.").format(
					frappe.bold(domain), frappe.bold(tenant_name)
				)
			)


def ensure_groups_belong_to_tenant(tenant: str, groups: list[str]) -> None:
	"""Ensure that the groups belong to the given tenant."""

	tenant_groups = get_tenant_groups(tenant)
	tenant_name = frappe.db.get_value("Mail Tenant", tenant, "tenant_name")

	for group in groups:
		if group not in tenant_groups:
			frappe.throw(
				_("Group {0} is not associated with tenant {1}.").format(
					frappe.bold(group), frappe.bold(tenant_name)
				)
			)


def ensure_lists_belong_to_tenant(tenant: str, lists: list[str]) -> None:
	"""Ensure that the lists belong to the given tenant."""

	tenant_lists = get_tenant_mailing_lists(tenant)
	tenant_name = frappe.db.get_value("Mail Tenant", tenant, "tenant_name")

	for lst in lists:
		if lst not in tenant_lists:
			frappe.throw(
				_("List {0} is not associated with tenant {1}.").format(
					frappe.bold(lst), frappe.bold(tenant_name)
				)
			)


def ensure_members_belong_to_tenant(tenant: str, members: list[str]) -> None:
	"""Ensure that the members belong to the given tenant."""

	tenant_emails = frappe.db.get_all(
		"Mail Principal Binding",
		filters={"tenant": tenant, "principal_type": ["in", ["Group", "Individual"]]},
		pluck="principal_name",
	)
	tenant_name = frappe.db.get_value("Mail Tenant", tenant, "tenant_name")

	for member in members:
		if member not in tenant_emails:
			frappe.throw(
				_("Member {0} is not associated with tenant {1}.").format(
					frappe.bold(member), frappe.bold(tenant_name)
				)
			)


def validate_wildcard_email(email: str, raise_exception: bool = True) -> bool:
	"""Returns True if the email contains wildcard characters."""

	wildcards = ["*", "?", "%"]
	if any(w in email for w in wildcards):
		if raise_exception:
			frappe.throw(
				_("Wildcard characters ({0}) are not allowed in email addresses.").format(
					", ".join(frappe.bold(w) for w in wildcards)
				)
			)

		return True
	return False
