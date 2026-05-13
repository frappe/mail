import os
import re

import frappe
from croniter import CroniterBadCronError, croniter
from frappe import _
from frappe.utils import cint
from frappe.utils.caching import request_cache

from mail.utils import get_config


def is_subaddressed_email(email: str, raise_exception: bool = False) -> bool:
	"""Returns True if the email address contains subaddressing else False."""

	if re.search(r"[^@]+\+[^@]+@", email):
		if raise_exception:
			frappe.throw(_("Subaddressing is not allowed in the email address."))

		return True
	return False


def is_email_assigned(email: str, raise_exception: bool = False) -> bool:
	"""Returns True if the email address is already assigned else False."""

	if frappe.db.exists("Principal Settings", {"principal_name": email}):
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


@request_cache
def validate_domain_is_verified(domain_name: str) -> None:
	"""Validates if the domain is verified."""

	if not frappe.db.exists("Principal Settings", {"principal_name": domain_name, "is_verified": 1}):
		frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(domain_name)))


@request_cache
def validate_local_domain(domain_name: str) -> None:
	if not frappe.db.exists(
		"Principal Settings", {"principal_type": "Domain", "principal_name": domain_name}
	):
		frappe.throw(_("Domain {0} not found.").format(frappe.bold(domain_name)))


def validate_max_domains() -> None:
	"""Validates if the maximum number of domains has been reached."""

	max_domains = cint(get_config("max_domains"))
	if max_domains <= 0:
		return

	total_domains = frappe.db.count("Principal Settings", {"principal_type": "Domain"})

	if total_domains >= max_domains:
		frappe.throw(_("You have reached the maximum limit of {0} domains.").format(frappe.bold(max_domains)))


def validate_max_groups() -> None:
	"""Validates if the maximum number of groups has been reached."""

	max_groups = cint(get_config("max_groups"))
	if max_groups <= 0:
		return

	total_groups = frappe.db.count("Principal Settings", {"principal_type": "Group"})

	if total_groups >= max_groups:
		frappe.throw(_("You have reached the maximum limit of {0} groups.").format(frappe.bold(max_groups)))


def validate_max_accounts() -> None:
	"""Validates if the maximum number of accounts has been reached."""

	max_accounts = cint(get_config("max_accounts"))
	if max_accounts <= 0:
		return

	total_accounts = frappe.db.count("Principal Settings", {"principal_type": "Individual"})

	if total_accounts >= max_accounts:
		frappe.throw(
			_("You have reached the maximum limit of {0} accounts.").format(frappe.bold(max_accounts))
		)


def validate_max_lists() -> None:
	"""Validates if the maximum number of lists has been reached."""

	max_lists = cint(get_config("max_lists"))
	if max_lists <= 0:
		return

	total_lists = frappe.db.count("Principal Settings", {"principal_type": "List"})

	if total_lists >= max_lists:
		frappe.throw(_("You have reached the maximum limit of {0} lists.").format(frappe.bold(max_lists)))


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
	base_dir: str, required_files: list[str] | None = None, raise_exception: bool = False
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

	from mail.utils.user import is_administrator

	current_user = frappe.session.user
	has_permission = user == current_user or is_administrator(current_user)

	if not has_permission and raise_exception:
		frappe.throw(_("You do not have permission to access this resource."), frappe.PermissionError)

	return has_permission


def validate_mail_config() -> None:
	"""Validates the mail configuration. Checks if the server URL is set and if the fallback admin credentials are set."""

	config = get_config()
	if not config:
		frappe.throw(_("Mail configuration is not set."))

	if not config.get("server_url"):
		frappe.throw(_("Mail server URL is not set in Mail Configuration."))

	api_key = config.get("api_key")

	username = config.get("username")
	password = config.get("password")

	if not api_key and not (username and password):
		frappe.throw(_("Admin credentials are not set in Mail Configuration."))


def ensure_local_user(user: str) -> None:
	"""Ensures that the user is a managed user."""

	from mail.utils.user import is_local_user

	if not is_local_user(user):
		frappe.throw(_("User {0} is not a local user.").format(frappe.bold(user)))


def ensure_access_to_backend() -> None:
	"""Ensures that the current user has access to the mail backend."""

	from mail.utils.user import is_mail_admin, is_system_manager

	user = frappe.session.user
	if not is_mail_admin(user) and not is_system_manager(user):
		frappe.throw(_("You do not have permission to access the mail backend."), frappe.PermissionError)


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
