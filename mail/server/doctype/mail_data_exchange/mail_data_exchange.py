# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import os
import re
import shlex
import shutil
from typing import Literal
from uuid import uuid7

import frappe
import pexpect
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils import add_to_date, cint, get_bench_path, get_datetime, get_url, now, time_diff_in_seconds

from mail.client.doctype.push_subscription.push_subscription import (
	freeze_jmap_push_notifications,
	unfreeze_jmap_push_notifications,
)
from mail.utils import (
	compress_directory,
	extract_compressed_file,
	get_config,
	get_data_export_directory,
	get_data_import_directory,
	get_mbox_files,
	get_stalwart_cli_path,
	reconnect_on_failure,
	sanitize_cli_output,
)
from mail.utils.user import (
	clear_sync_state,
	get_jmap_username,
	get_user_email_address,
	is_administrator,
	is_mail_admin,
	is_system_manager,
)
from mail.utils.validation import (
	ensure_local_user,
	validate_jmap_structure,
	validate_mail_config,
	validate_maildir_or_maildirpp,
	validate_nested_maildir_tree,
)


class MailDataExchange(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		if self.is_new():
			self.validate_user()

		if self.operation == "Import":
			self.validate_import()
		elif self.operation == "Export":
			self.validate_export()

	def before_submit(self) -> None:
		self.status = "Queued"
		self.queued_at = now()

	def on_submit(self) -> None:
		self.process()

	def before_cancel(self) -> None:
		self.status = "Cancelled"

	def validate_user(self) -> None:
		"""Validate the user."""

		ensure_local_user(self.user)

	def validate_import(self) -> None:
		"""Validate the import parameters."""

		if not self.import_format:
			frappe.throw(_("Import Format is required."))
		if not self.import_file:
			frappe.throw(_("Import File is required."))

		allowed_extensions = [".zip", ".tgz", ".tar.gz"]
		if not self.import_file.endswith(tuple(allowed_extensions)):
			frappe.throw(
				_("Only {0} files are supported for import.").format(
					", ".join(f"<code>{ext}</code>" for ext in allowed_extensions)
				)
			)

	def validate_export(self) -> None:
		"""Validate the export parameters."""

		if not self.export_archive_type:
			frappe.throw(_("Archive Type is required."))

	def process(self) -> None:
		"""Enqueue the import or export based on the operation type."""

		if self.operation == "Import":
			job_id = f"{self.name}:data:import"
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"_import",
				queue="long",
				timeout=cint(get_config("data_exchange_import_timeout")),
				job_id=job_id,
				deduplicate=True,
				enqueue_after_commit=True,
			)
		elif self.operation == "Export":
			job_id = f"{self.name}:data:export"
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"_export",
				queue="long",
				timeout=cint(get_config("data_exchange_export_timeout")),
				job_id=job_id,
				deduplicate=True,
				enqueue_after_commit=True,
			)

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retry the import or export."""

		frappe.only_for("System Manager")

		if self.docstatus != 1:
			frappe.throw(_("Only submitted data exchange can be retried."))
		elif self.status not in ["Queued", "In Progress", "Failed"]:
			frappe.throw(
				_("Only data exchange with status 'Queued', 'In Progress', or 'Failed' can be retried.")
			)

		if self.operation == "Export":
			if files := frappe.db.get_all(
				"File",
				{
					"attached_to_doctype": self.doctype,
					"attached_to_name": self.name,
					"attached_to_field": "file",
				},
				pluck="name",
			):
				for file in files:
					frappe.delete_doc("File", file)

		self._db_set(status="Queued", queued_at=now())
		self.process()

	def _import(self) -> None:
		"""Imports the account data."""

		if self.operation != "Import":
			return

		freeze_jmap_push_notifications(self.user)
		self._mark_started()

		import_file = os.path.join(get_bench_path(), f"sites/{frappe.local.site}{self.import_file}")
		base_dir = os.path.join(get_data_import_directory(), self.name)
		os.makedirs(base_dir, exist_ok=True)

		kwargs = {}
		try:
			cli_path = get_stalwart_cli_path()
			extract_compressed_file(import_file, base_dir)
			host, _credentials = self._get_host_and_credentials()

			command = [cli_path, "-u", host, "import"]
			if self.import_format == "jmap":
				command.append("account")
			else:
				command.extend(["messages", "-f", self.import_format])
			command.append(get_jmap_username(self.user))

			if self.import_format == "jmap":
				validate_jmap_structure(base_dir, raise_exception=True)
				command.append(base_dir)
			elif self.import_format == "mbox":
				mbox_files = get_mbox_files(base_dir)

				if len(mbox_files) == 0:
					frappe.throw(_("No {0} file found in the archive.").format("<code>.mbox</code>"))
				elif len(mbox_files) > 1:
					frappe.throw(
						_("Multiple {0} files found. Please provide only one.").format("<code>.mbox</code>")
					)

				command.append(mbox_files[0])
			else:
				if self.import_format == "maildir":
					validate_maildir_or_maildirpp(base_dir, raise_exception=True)
				elif self.import_format == "maildir-nested":
					validate_nested_maildir_tree(base_dir, raise_exception=True)

				command.append(base_dir)

			output = _run_stalwart_cli_command(command, _credentials)

			try:
				output = clean_import_output(output)
			except Exception:
				frappe.log_error(
					title=_("Failed to clean import output"), message=frappe.get_traceback(with_context=True)
				)

			clear_sync_state(self.user, type="email")
			kwargs.update({"status": "Completed", "output": output})
		except Exception:
			kwargs.update({"status": "Failed", "output": frappe.get_traceback(with_context=False)})
		finally:
			shutil.rmtree(base_dir, ignore_errors=True)
			unfreeze_jmap_push_notifications(self.user)

		self._mark_completed(**kwargs)
		self._notify_user(success=kwargs.get("status") == "Completed", action="Import")

	def _export(self) -> None:
		"""Exports the account data."""

		if self.operation != "Export":
			return

		self._mark_started()
		out_dir = os.path.join(get_data_export_directory(), self.name)
		os.makedirs(out_dir, exist_ok=True)

		kwargs = {}
		try:
			cli_path = get_stalwart_cli_path()
			host, _credentials = self._get_host_and_credentials()
			command = f"{cli_path} -u {host} export account {get_jmap_username(self.user)} {out_dir}"
			output = _run_stalwart_cli_command(command, _credentials)
			self._attach_export(out_dir)
			kwargs.update({"status": "Completed", "output": output})
		except Exception:
			kwargs.update({"status": "Failed", "output": frappe.get_traceback(with_context=False)})
		finally:
			shutil.rmtree(out_dir, ignore_errors=True)

		self._mark_completed(**kwargs)
		self._notify_user(success=kwargs.get("status") == "Completed", action="Export")

	def _mark_started(self) -> None:
		"""Marks the data exchange as started and updates the started_at and started_after fields."""

		started_at = now()
		self._db_set(
			status="In Progress",
			started_at=started_at,
			started_after=time_diff_in_seconds(started_at, self.queued_at),
		)

	def _get_host_and_credentials(self) -> tuple[str, str]:
		"""Returns the host and credentials for the user's cluster."""

		validate_mail_config()
		config = get_config()

		return (config["server_url"], f"{config['username']}:{config['password']}")

	def _mark_completed(self, **kwargs) -> None:
		"""Marks the data exchange as completed and updates the completed_at and duration fields."""

		kwargs["completed_at"] = now()
		kwargs["duration"] = time_diff_in_seconds(kwargs["completed_at"], self.started_at)

		if kwargs["status"] == "Failed":
			kwargs["retries"] = cint(self.retries) + 1

		self._db_set(**kwargs)

	def _attach_export(self, out_dir: str) -> None:
		"""Attaches the exported file to the data exchange."""

		archive = f"{self.name}{self.export_archive_type}"
		url = f"/private/files/{archive}"
		path = os.path.join(get_bench_path(), f"sites/{frappe.local.site}{url}")
		compress_directory(os.path.join(out_dir, get_jmap_username(self.user)), path)

		file = frappe.new_doc("File")
		file.is_private = 1
		file.file_url = url
		file.file_name = archive
		file.attached_to_doctype = self.doctype
		file.attached_to_name = self.name
		file.attached_to_field = "file"
		file.insert()

		# https://github.com/frappe/frappe/issues/26615
		frappe.db.set_value("File", file.name, {"file_url": url, "file_name": archive})

	@reconnect_on_failure()
	def _notify_user(self, success: bool, action: Literal["Import", "Export"]) -> None:
		"""Sends notification email to the owner of the data exchange."""

		if is_administrator(self.owner):
			return
		if not (email := get_user_email_address(self.owner)):
			return

		subject = _("Mail Data {0} {1}").format(action, "Completed" if success else "Failed")
		frappe.sendmail(
			recipients=email,
			subject=subject,
			template="generic",
			args={
				"title": subject,
				"description": _("View details for this exchange."),
				"button": _("View {0}").format(action),
				"link": get_url(f"/mail/mail-data-exchanges/{self.name}"),
			},
			now=True,
		)

	@reconnect_on_failure()
	def _db_set(self, **kwargs) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, notify=True, commit=True)


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user) or is_mail_admin(user):
		return ""

	return f"(`tabMail Data Exchange`.user = '{user}')"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Data Exchange":
		return False

	user = user or frappe.session.user

	if is_system_manager(user) or is_mail_admin(user):
		return True

	return doc.user == user


def _run_stalwart_cli_command(command: str | list[str], _credentials: str, timeout: int | None = None) -> str:
	"""Runs the stalwart CLI command with the provided credentials and returns the output."""

	if isinstance(command, list):
		command = " ".join(shlex.quote(arg) for arg in command)

	timeout = timeout or cint(get_config("stalwart_cli_command_timeout"))
	child = pexpect.spawn(command, encoding="utf-8", timeout=timeout)
	child.expect("Enter administrator credentials or press \\[ENTER\\] to use OAuth:")
	child.sendline(_credentials)
	child.expect(pexpect.EOF)
	child.wait()
	output = child.before.strip() if child.before else "No output received."

	if child.exitstatus != 0:
		raise Exception(output)

	return output


def clean_import_output(output: str) -> str:
	"""Cleans the output of the import operation."""

	if output:
		output = sanitize_cli_output(output)

		cleaned_lines = []
		for line in output.splitlines():
			stripped = line.strip()
			if not stripped:
				continue

			# Keep only lines like "[n/m] ..." or "Successfully imported ..."
			if re.match(r"^\[\d+/\d+\]\s+.+", stripped) or stripped.startswith("Successfully imported"):
				cleaned_lines.append(stripped)

		return "\n".join(cleaned_lines)

	return output


def retry_stuck_data_exchanges() -> None:
	"""Called by the scheduler to retry stuck data exchanges."""

	DE = frappe.qb.DocType("Mail Data Exchange")
	exchanges = (
		frappe.qb.from_(DE)
		.select(DE.name)
		.where(
			(DE.status.isin(["Queued", "In Progress"]))
			& (DE.queued_at <= get_datetime(add_to_date(now(), hours=-1)))
		)
		.orderby(DE.queued_at, order=Order.asc)
	).run(pluck="name")

	if not exchanges:
		return

	for exchange in exchanges:
		doc = frappe.get_doc("Mail Data Exchange", exchange)
		doc.retry()


def clean_import_export_directories() -> None:
	"""Called by the scheduler to clean up import and export directories."""

	for directory in (get_data_import_directory(), get_data_export_directory()):
		if os.path.exists(directory):
			for item in os.listdir(directory):
				item_path = os.path.join(directory, item)
				if os.path.isdir(item_path):
					if frappe.db.exists("Mail Data Exchange", {"name": item, "status": "In Progress"}):
						continue

					shutil.rmtree(item_path, ignore_errors=True)
				else:
					os.remove(item_path)
