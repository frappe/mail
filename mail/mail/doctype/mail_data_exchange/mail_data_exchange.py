# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import os
import re
import shlex
import shutil

import frappe
import pexpect
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils import add_to_date, cint, get_bench_path, get_datetime, get_url, now, time_diff_in_seconds
from uuid_utils import uuid7

from mail.client.doctype.jmap_push_subscription.jmap_push_subscription import (
	freeze_jmap_push_notifications,
	unfreeze_jmap_push_notifications,
)
from mail.client.doctype.jmap_sync_state.jmap_sync_state import clear_jmap_sync_state
from mail.utils import (
	compress_directory,
	extract_compressed_file,
	get_export_directory,
	get_import_directory,
	get_mbox_files,
	get_stalwart_cli_path,
	reconnect_on_failure,
	sanitize_cli_output,
)
from mail.utils.cache import get_account_for_user, get_tenant_for_user
from mail.utils.user import has_role, is_account_owner, is_system_manager, is_tenant_admin
from mail.utils.validation import (
	validate_jmap_structure,
	validate_maildir_or_maildirpp,
	validate_nested_maildir_tree,
)


class MailDataExchange(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		if self.operation == "Import":
			self.validate_import_format()
			self.validate_import_file()
		elif self.operation == "Export":
			self.validate_export_archive_type()

	def before_submit(self) -> None:
		self.status = "Queued"
		self.queued_at = now()

	def on_submit(self) -> None:
		self.process()

	def before_cancel(self) -> None:
		self.status = "Cancelled"

	def validate_import_format(self) -> None:
		"""Validate the import format."""

		if not self.import_format:
			frappe.throw(_("Import Format is required."))

	def validate_import_file(self) -> None:
		"""Validate the import file."""

		if not self.import_file:
			frappe.throw(_("Import File is required."))

		allowed_extensions = [".zip", ".tgz", ".tar.gz"]
		if not self.import_file.endswith(tuple(allowed_extensions)):
			frappe.throw(
				_("Only {0} files are supported for import.").format(
					", ".join(f"<code>{ext}</code>" for ext in allowed_extensions)
				)
			)

	def validate_export_archive_type(self) -> None:
		"""Validate the export archive type."""

		if not self.export_archive_type:
			frappe.throw(_("Archive Type is required."))

	def process(self) -> None:
		"""Enqueue the import or export based on the operation type."""

		if self.operation == "Import":
			job_id = f"{self.name}:import"
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"_import",
				queue="long",
				timeout=cint(frappe.conf.data_exchange_import_timeout) or 3600,
				job_id=job_id,
				deduplicate=True,
				enqueue_after_commit=True,
			)
		elif self.operation == "Export":
			job_id = f"{self.name}:export"
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"_export",
				queue="long",
				timeout=cint(frappe.conf.data_exchange_export_timeout) or 3600,
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

		self._db_set(status="Queued", queued_at=now(), notify=True)
		self.process()

	@reconnect_on_failure()
	def _import(self) -> None:
		"""Imports the account data."""

		if self.operation != "Import":
			return

		freeze_jmap_push_notifications(self.account)
		self._mark_started()

		import_file = os.path.join(get_bench_path(), f"sites/{frappe.local.site}{self.import_file}")
		import_base = os.path.join(get_import_directory(), self.name)
		os.makedirs(import_base, exist_ok=True)

		kwargs = {}
		try:
			cli_path = get_stalwart_cli_path()
			extract_compressed_file(import_file, import_base)
			host, _credentials = self._get_host_and_credentials()

			command = [cli_path, "-u", host, "import"]
			if self.import_format == "jmap":
				command.append("account")
			else:
				command.extend(["messages", "-f", self.import_format])
			command.append(self.account)

			if self.import_format == "mbox":
				mbox_files = get_mbox_files(import_base)

				if len(mbox_files) == 0:
					frappe.throw(_("No {0} file found in the archive.").format("<code>.mbox</code>"))
				elif len(mbox_files) > 1:
					frappe.throw(
						_("Multiple {0} files found. Please provide only one.").format("<code>.mbox</code>")
					)

				command.append(mbox_files[0])
			elif self.import_format == "jmap":
				_import_base = os.path.join(import_base, self.account)
				validate_jmap_structure(_import_base, raise_exception=True)
				command.append(_import_base)
			else:
				if self.import_format == "maildir":
					validate_maildir_or_maildirpp(import_base, raise_exception=True)
				elif self.import_format == "maildir-nested":
					validate_nested_maildir_tree(import_base, raise_exception=True)

				command.append(import_base)

			output = _run_stalwart_cli_command(command, _credentials)

			try:
				output = clean_import_output(output)
			except Exception:
				frappe.log_error(
					title=_("Failed to clean import output"), message=frappe.get_traceback(with_context=True)
				)

			clear_jmap_sync_state(self.account)
			kwargs.update({"status": "Completed", "output": output})

			mail_details = {
				"subject": _("Mail Data Import Completed"),
				"title": _("Mail data import for account {0} has been completed successfully.").format(
					frappe.bold(self.account)
				),
				"description": _("Click the button below to view the imported data."),
			}

		except Exception as e:
			kwargs.update({"status": "Failed", "output": str(e)})

			mail_details = {
				"subject": _("Mail Data Import Failed"),
				"title": _("Mail data import for account {0} has failed.").format(frappe.bold(self.account)),
				"description": _("Click the button below to view the reason for failure."),
			}

		shutil.rmtree(import_base, ignore_errors=True)
		self._mark_completed(**kwargs)
		unfreeze_jmap_push_notifications(self.account)

		if account := get_account_for_user(self.owner):
			frappe.sendmail(
				recipients=account,
				subject=mail_details["subject"],
				template="generic",
				args={
					"title": mail_details["title"],
					"description": mail_details["description"],
					"button": _("View Import"),
					"link": get_url(f"/mail/mail-data-exchanges/{self.name}"),
				},
				now=True,
			)

	@reconnect_on_failure()
	def _export(self) -> None:
		"""Exports the account data."""

		if self.operation != "Export":
			return

		self._mark_started()
		export_base = os.path.join(get_export_directory(), self.name)
		export_file_name = f"{self.name}{self.export_archive_type}"
		export_file_url = f"/private/files/{export_file_name}"
		export_file = os.path.join(get_bench_path(), f"sites/{frappe.local.site}{export_file_url}")
		os.makedirs(export_base, exist_ok=True)

		kwargs = {}
		try:
			cli_path = get_stalwart_cli_path()
			host, _credentials = self._get_host_and_credentials()
			command = f"{cli_path} -u {host} export account {self.account} {export_base}"
			output = _run_stalwart_cli_command(command, _credentials)

			compress_directory(export_base, export_file)
			file = frappe.new_doc("File")
			file.is_private = 1
			file.file_url = export_file_url
			file.file_name = export_file_name
			file.attached_to_doctype = self.doctype
			file.attached_to_name = self.name
			file.attached_to_field = "file"
			file.insert()

			# https://github.com/frappe/frappe/issues/26615
			frappe.db.set_value(
				"File", file.name, {"file_url": export_file_url, "file_name": export_file_name}
			)

			kwargs.update({"status": "Completed", "output": output})

			mail_details = {
				"subject": _("Mail Data Export Ready"),
				"title": _("Mail data export for account {0} is ready for download.").format(
					frappe.bold(self.account)
				),
				"description": _("Click the button below to view and download the exported data."),
			}

		except Exception as e:
			kwargs.update({"status": "Failed", "output": str(e)})

			mail_details = {
				"subject": _("Mail Data Export Failed"),
				"title": _("Mail data export for account {0} has failed.").format(frappe.bold(self.account)),
				"description": _("Click the button below to view the reason for failure."),
			}

		shutil.rmtree(export_base, ignore_errors=True)
		self._mark_completed(**kwargs)

		if account := get_account_for_user(self.owner):
			frappe.sendmail(
				recipients=account,
				subject=mail_details["subject"],
				template="generic",
				args={
					"title": mail_details["title"],
					"description": mail_details["description"],
					"button": _("View Export"),
					"link": get_url(f"/mail/mail-data-exchanges/{self.name}"),
				},
				now=True,
			)

	def _mark_started(self) -> None:
		"""Marks the data exchange as started and updates the started_at and started_after fields."""

		started_at = now()
		started_after = time_diff_in_seconds(started_at, self.queued_at)
		self._db_set(
			status="In Progress", started_at=started_at, started_after=started_after, notify=True, commit=True
		)

	def _get_host_and_credentials(self) -> tuple[str, str]:
		"""Returns the host and credentials for the account's cluster."""

		tenant = frappe.db.get_value("Mail Account", self.account, "tenant")
		cluster = frappe.get_doc("Mail Cluster", frappe.db.get_value("Mail Tenant", tenant, "cluster"))

		return (
			cluster.base_url,
			f"{cluster.fallback_admin_user}:{cluster.get_password('fallback_admin_password')}",
		)

	def _mark_completed(self, **kwargs) -> None:
		"""Marks the data exchange as completed and updates the completed_at and duration fields."""

		kwargs["completed_at"] = now()
		kwargs["duration"] = time_diff_in_seconds(kwargs["completed_at"], self.started_at)

		if kwargs["status"] == "Failed":
			kwargs["retries"] = cint(self.retries) + 1

		self._db_set(notify=True, **kwargs)

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user):
		return ""

	if has_role(user, "Mail Admin"):
		if tenant := get_tenant_for_user(user):
			return f"(`tabMail Data Exchange`.tenant = '{tenant}')"

	if has_role(user, "Mail User"):
		if account := get_account_for_user(user):
			return f"(`tabMail Data Exchange`.account = '{account}')"

	return "1=0"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Data Exchange":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True
	elif has_role(user, "Mail Admin"):
		return is_tenant_admin(doc.tenant, user)
	elif has_role(user, "Mail User"):
		return is_account_owner(doc.account, user)

	return False


def _run_stalwart_cli_command(command: str | list[str], _credentials: str, timeout: int | None = None) -> str:
	"""Runs the stalwart CLI command with the provided credentials and returns the output."""

	if isinstance(command, list):
		command = " ".join(shlex.quote(arg) for arg in command)

	timeout = timeout or cint(frappe.conf.stalwart_cli_command_timeout) or 3600
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

	for directory in (get_import_directory(), get_export_directory()):
		if os.path.exists(directory):
			for item in os.listdir(directory):
				item_path = os.path.join(directory, item)
				if os.path.isdir(item_path):
					if frappe.db.exists("Mail Data Exchange", {"name": item, "status": "In Progress"}):
						continue

					shutil.rmtree(item_path, ignore_errors=True)
				else:
					os.remove(item_path)
