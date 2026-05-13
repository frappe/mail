import os
import platform
import subprocess
import tarfile
import urllib.request
from typing import TYPE_CHECKING

import frappe
from frappe import _

from mail.utils import get_config, get_mail_app_path, get_stalwart_cli_path, get_stalwart_cli_version

if TYPE_CHECKING:
	from subprocess import CompletedProcess


class StalwartCLI:
	def __init__(self, credentials: dict[str, str] | None = None) -> None:
		if credentials:
			self._validate_credentials(credentials)
			self._credentials = credentials

		else:
			config = get_config()
			credentials = {
				"server_url": config.get("server_url"),
				"username": config.get("username"),
				"password": config.get("password"),
			}
			self._validate_credentials(credentials)

		self._credentials = credentials
		self.cli_path = get_stalwart_cli_path()

		if not os.path.exists(self.cli_path):
			self._install()

	def _url(self) -> tuple[str, str]:
		"""Returns the download URL and filename for the appropriate Stalwart CLI release based on the current platform and architecture."""

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
			frappe.throw(_("Unsupported architecture: {0}").format(arch))

		if system == "linux":
			os_id = "unknown-linux-gnu"
		elif system == "darwin":
			os_id = "apple-darwin"
		else:
			frappe.throw(_("Unsupported operating system: {0}").format(system))

		filename = f"stalwart-cli-{arch}-{os_id}.tar.xz"
		return f"{github_release_base}/{filename}", filename

	def _install(self) -> None:
		"""Downloads and installs the Stalwart CLI to the mail app directory."""

		print("Installing Stalwart CLI...")

		url, filename = self._url()
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

		os.chmod(self.cli_path, 0o755)

		if frappe.conf.developer_mode:
			print(f"\tRemoving {tar_path}...")

		os.remove(tar_path)

		if frappe.conf.developer_mode:
			print(f"\tStalwart CLI installed at: {self.cli_path}")

	def _validate_credentials(self, credentials: dict) -> None:
		"""Validates that the provided credentials contain all mandatory fields."""

		if frappe.flags.in_migrate:
			return

		mandatory_fields = ["server_url", "username", "password"]
		for field in mandatory_fields:
			if field not in credentials or not credentials[field]:
				frappe.throw(_("Missing mandatory credential field: {0}").format(field))

	def _parse_process_result(self, result: "CompletedProcess") -> dict:
		"""Parses the result of a subprocess execution and returns a dictionary with success status and output or error message."""

		if result.returncode == 0:
			return {"success": True, "output": result.stdout.strip()}
		else:
			return {"success": False, "error": result.stderr.strip()}

	def run(self, args: list[str]) -> dict:
		"""Runs a Stalwart CLI command with the provided arguments and returns the result."""

		cmd = [
			self.cli_path,
			"--url",
			self._credentials["server_url"],
			"--user",
			self._credentials["username"],
			"--password",
			self._credentials["password"],
			*args,
		]

		result = subprocess.run(cmd, capture_output=True, text=True)
		return self._parse_process_result(result)
