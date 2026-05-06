import os
import platform
import tarfile
import urllib.request

import frappe
from frappe.core.api.file import create_new_folder

from mail.mail.doctype.rate_limit.rate_limit import create_rate_limit
from mail.utils import get_mail_app_path, get_stalwart_cli_path, get_stalwart_cli_version


def after_install() -> None:
	add_rate_limits()
	create_new_folder("Frappe Mail", "Home")
	generate_jmap_push_keys()


def after_migrate() -> None:
	install_stalwart_cli()


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
		{"method_path": "mail.api.admin.verify_dns_record", "limit": 10, "seconds": 60 * 60},
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


def install_stalwart_cli() -> str:
	"""Download and install the Stalwart CLI tool."""

	print("Installing Stalwart CLI...")

	url, filename = _get_stalwart_cli_download_url()
	install_dir = get_mail_app_path()
	tar_path = os.path.join(install_dir, filename)

	if frappe.conf.developer_mode:
		print(f"\tDownloading {url}...")

	urllib.request.urlretrieve(url, tar_path)

	if frappe.conf.developer_mode:
		print(f"\tExtracting stalwart-cli from {filename}...")

	with tarfile.open(tar_path, "r:xz") as tar:
		member = next(
			(m for m in tar.getmembers() if os.path.basename(m.name) == "stalwart-cli"),
			None,
		)

		if not member:
			raise FileNotFoundError("stalwart-cli not found in archive")

		member.name = "stalwart-cli"
		tar.extract(member, path=install_dir)

	cli_path = get_stalwart_cli_path()
	os.chmod(cli_path, 0o755)

	if frappe.conf.developer_mode:
		print(f"\tRemoving {tar_path}...")

	os.remove(tar_path)

	if frappe.conf.developer_mode:
		print(f"\tStalwart CLI installed at: {cli_path}")

	return cli_path


def _get_stalwart_cli_download_url() -> str:
	"""Returns the download URL and filename for the Stalwart CLI tool."""

	version = get_stalwart_cli_version()
	github_release_base = (
		"https://github.com/stalwartlabs/cli/releases/latest/download"
		if version == "latest"
		else f"https://github.com/stalwartlabs/cli/releases/download/{version}"
	)

	system = platform.system().lower()
	arch = platform.machine().lower()

	if arch in ["x86_64", "amd64"]:
		arch = "x86_64"
	elif arch in ["arm64", "aarch64"]:
		arch = "aarch64"
	else:
		frappe.throw(f"Unsupported architecture: {arch}")

	if system == "linux":
		os_id = "unknown-linux-gnu"
	elif system == "darwin":
		os_id = "apple-darwin"
	else:
		raise Exception(f"Unsupported operating system: {system}")

	filename = f"stalwart-cli-{arch}-{os_id}.tar.xz"
	return f"{github_release_base}/{filename}", filename
