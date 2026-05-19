import os
import platform
import subprocess
import tarfile
import urllib.request
from typing import TYPE_CHECKING

import frappe
from frappe import _

from mail.utils import (
	get_config,
	get_mail_app_path,
	get_stalwart_cli_path,
	get_stalwart_cli_version,
	is_stalwart_configured,
)

if TYPE_CHECKING:
	from subprocess import CompletedProcess


class StalwartCLI:
	def __init__(self, credentials: dict[str, str] | None = None) -> None:
		credentials = credentials or {}

		if credentials:
			credentials = {
				"server_url": credentials.get("server_url"),
				"api_key": credentials.get("api_key"),
				"username": credentials.get("username"),
				"password": credentials.get("password"),
			}

			if not credentials.get("server_url"):
				frappe.throw(_("Server URL is required for Stalwart CLI operations."))
			if not credentials.get("api_key") and (
				not credentials.get("username") or not credentials.get("password")
			):
				frappe.throw(
					_("Either API key or username and password are required for Stalwart CLI operations.")
				)

		elif not frappe.flags.in_migrate:
			is_stalwart_configured(raise_exception=True)

			config = get_config()
			credentials = {
				"server_url": config["server_url"],
				"api_key": config["api_key"],
				"username": config["username"],
				"password": config["password"],
			}

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

	def _parse_process_result(self, result: "CompletedProcess") -> dict:
		"""Parses the result of a subprocess execution and returns a dictionary with success status and output or error message."""

		stdout = result.stdout.strip() if result.stdout else ""
		stderr = result.stderr.strip() if result.stderr else ""

		return {"success": result.returncode == 0, "output": stdout, "error": stderr}

	def run(self, args: list[str]) -> dict:
		"""Runs a Stalwart CLI command with the provided arguments and returns the result."""

		cmd = [self.cli_path, "--url", self._credentials["server_url"]]

		if self._credentials.get("api_key"):
			cmd.extend(["--api-key", self._credentials["api_key"]])
		else:
			cmd.extend(
				[
					"--user",
					self._credentials["username"],
					"--password",
					self._credentials["password"],
				]
			)

		cmd.extend(args)

		result = subprocess.run(cmd, capture_output=True, text=True)
		return self._parse_process_result(result)
