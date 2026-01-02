# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import mailbox
import os
import shutil
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Literal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.utils import (
	add_to_date,
	cint,
	create_batch,
	get_bench_path,
	get_datetime,
	get_url,
	now,
	time_diff_in_seconds,
)
from uuid_utils import uuid7

from mail.client.doctype.push_subscription.push_subscription import (
	freeze_jmap_push_notifications,
	unfreeze_jmap_push_notifications,
)
from mail.jmap import get_jmap_client
from mail.utils import (
	compress_directory,
	extract_compressed_file,
	get_mail_export_directory,
	get_mail_import_directory,
	get_mbox_files,
)
from mail.utils.cache import get_tenant_for_user
from mail.utils.user import (
	clear_sync_state,
	get_account_for_user,
	get_user_email_address,
	has_role,
	is_administrator,
	is_system_manager,
	is_tenant_admin,
)
from mail.utils.validation import (
	validate_jmap_structure,
	validate_maildir_or_maildirpp,
	validate_nested_maildir_tree,
)


@dataclass
class ImportMeta:
	blob_path: str
	mailbox_ids: set[str]
	keywords: set[str] | None
	received_at: datetime | None


@dataclass
class ExportEmail:
	id: str
	sender: dict[str, str]
	blob_id: str
	keywords: set[str]
	mailbox_ids: set[str]
	message_id: str
	received_at: datetime
	raw: bytes


class MetadataLoader:
	@staticmethod
	def load(
		format: Literal["eml", "jmap", "mbox", "maildir", "maildir-nested"],
		input_directory: str,
		mailbox_map: dict[str, str],
		metadata: dict,
	) -> list[ImportMeta]:
		"""Loads the email metadata based on the specified format."""

		if format == "eml":
			return MetadataLoader._get_eml_metadata(input_directory, metadata)
		elif format == "jmap":
			return MetadataLoader._get_jmap_metadata(input_directory)
		elif format == "mbox":
			return MetadataLoader._get_mbox_metadata(input_directory, mailbox_map)
		elif format == "maildir":
			return MetadataLoader._get_maildir_metadata(input_directory)
		elif format == "maildir-nested":
			return MetadataLoader._get_maildir_nested_metadata(input_directory)
		else:
			frappe.throw(_("Unsupported format: {0}").format(format))

	@staticmethod
	def load_metadata(input_directory: str) -> list[dict]:
		"""Loads email metadata from emails.json in the input directory."""

		meta_path = os.path.join(input_directory, "emails.json")
		if not os.path.exists(meta_path):
			frappe.throw(_("emails.json not found in the import directory."))

		with open(meta_path) as f:
			metadata = json.load(f)

		return metadata

	@staticmethod
	def _get_eml_metadata(input_directory: str, metadata: dict) -> list[ImportMeta]:
		"""Loads emails metadata for EML format located at input_directory."""

		if not metadata or not metadata.get("mailboxIds"):
			frappe.throw(_("mailboxIds are required in Metadata for EML format."))

		eml_files = [f for f in os.listdir(input_directory) if f.endswith(".eml")]
		if not eml_files:
			frappe.throw(_("mailboxIds are required in Metadata for EML format."))

		import_metadata: list[ImportMeta] = []
		mailbox_ids = set(metadata["mailboxIds"].keys())
		keywords = set(metadata.get("keywords", {}).keys()) if metadata.get("keywords") else None
		received_at = datetime.fromisoformat(metadata["receivedAt"]) if metadata.get("receivedAt") else None
		for eml_file in eml_files:
			import_meta = ImportMeta(
				blob_path=eml_file,
				mailbox_ids=mailbox_ids,
				keywords=keywords,
				received_at=received_at,
			)
			import_metadata.append(import_meta)

		return import_metadata

	@staticmethod
	def _get_jmap_metadata(input_directory: str) -> list[ImportMeta]:
		"""Loads emails metadata for JMAP format located at input_directory."""

		validate_jmap_structure(input_directory, ["emails.json"], raise_exception=True)

		import_metadata: list[ImportMeta] = []
		metadata = MetadataLoader.load_metadata(input_directory)
		for meta in metadata:
			import_meta = ImportMeta(
				blob_path=os.path.join("blobs", meta["blobId"]),
				mailbox_ids=set(meta["mailboxIds"].keys()),
				keywords=set(meta.get("keywords", {}).keys()) if meta.get("keywords") else None,
				received_at=datetime.fromisoformat(meta["receivedAt"]) if meta.get("receivedAt") else None,
			)
			import_metadata.append(import_meta)

		return import_metadata

	@staticmethod
	def _get_mbox_metadata(
		input_directory: str,
		mailbox_map: dict[str, str],
	) -> list[ImportMeta]:
		"""Loads emails metadata for MBOX format located at input_directory."""

		mbox_files = get_mbox_files(input_directory)
		if not mbox_files:
			frappe.throw(_("No {0} file found in the archive.").format("<code>.mbox</code>"))

		import_metadata_map: dict[str, ImportMeta] = {}
		for mbox_path in mbox_files:
			mailbox_id = next(
				(k for k, v in mailbox_map.items() if v + ".mbox" == os.path.basename(mbox_path)), None
			)

			if not mailbox_id:
				frappe.throw(_("Mailbox ID not found for MBOX file: {0}").format(os.path.basename(mbox_path)))

			with closing(mailbox.mbox(mbox_path, factory=None)) as mbox:
				for key, message in mbox.items():
					message_id = message.get("Message-ID") or key
					if message_id in import_metadata_map:
						import_metadata_map[message_id].mailbox_ids.add(mailbox_id)
						continue

					blob_filename = f"{uuid7()}.eml"
					with open(os.path.join(input_directory, blob_filename), "wb") as f:
						f.write(message.as_bytes(unixfrom=True))

					import_metadata_map[message_id] = ImportMeta(
						blob_path=blob_filename,
						mailbox_ids={mailbox_id},
						keywords=None,
						received_at=None,
					)

		return list(import_metadata_map.values())

	@staticmethod
	def _get_maildir_metadata(input_directory: str) -> list[ImportMeta]:
		"""Loads emails metadata for Maildir or Maildir++ format located at input_directory."""

		validate_maildir_or_maildirpp(input_directory, raise_exception=True)

	@staticmethod
	def _get_maildir_nested_metadata(input_directory: str) -> list[ImportMeta]:
		"""Loads emails metadata for Nested Maildir format located at input_directory."""

		validate_nested_maildir_tree(input_directory, raise_exception=True)


class MailWriter:
	FLAG_MAP: ClassVar[dict] = {
		"$seen": "S",
		"$flagged": "F",
		"$answered": "R",
		"$draft": "D",
	}

	@staticmethod
	def write(
		format: Literal["jmap", "mbox", "maildir", "maildir-nested"],
		export_emails: list[ExportEmail],
		output_directory: str,
		mailbox_map: dict[str, str],
	) -> None:
		"""Writes the exported emails to the specified format in the output directory."""

		if format == "jmap":
			MailWriter._write_jmap(export_emails, output_directory)
		elif format == "mbox":
			MailWriter._write_mbox(export_emails, output_directory, mailbox_map)
		elif format == "maildir":
			MailWriter._write_maildir(export_emails, output_directory)
		elif format == "maildir-nested":
			MailWriter._write_maildir_nested(export_emails, output_directory, mailbox_map)
		else:
			frappe.throw(_("Unsupported format: {0}").format(format))

	@staticmethod
	def write_metadata(metadata: list[dict], output_directory: str) -> None:
		"""Writes the email metadata to a JSON file in the output directory."""

		_metadata: list[dict] = []
		for meta in metadata:
			_metadata.append(
				{
					"id": meta["id"],
					"blobId": meta["blobId"],
					"keywords": meta["keywords"],
					"mailboxIds": meta["mailboxIds"],
					"messageId": meta["messageId"],
					"receivedAt": meta["receivedAt"],
				}
			)

		with open(os.path.join(output_directory, "emails.json"), "w") as f:
			json.dump(_metadata, f, indent=4)

	@staticmethod
	def _write_jmap(export_emails: list[ExportEmail], output_directory: str) -> None:
		"""Writes the exported emails in JMAP format."""

		blobs_dir = os.path.join(output_directory, "blobs")
		os.makedirs(blobs_dir, exist_ok=True)

		for export_email in export_emails:
			with open(os.path.join(blobs_dir, export_email.blob_id), "wb") as f:
				f.write(export_email.raw)

	@staticmethod
	def _write_mbox(
		export_emails: list[ExportEmail], output_directory: str, mailbox_map: dict[str, str]
	) -> None:
		"""Writes the exported emails in MBOX format."""

		def mbox_from_line(sender: dict[str, str], received_at: datetime) -> bytes:
			"""
			Builds an mbox 'From ' separator line.
			Example:
			From user@example.com Sat Jan  1 00:00:00 2026
			"""

			email = sender.get("email", "unknown")
			timestamp = received_at.timestamp()
			ctime_date = datetime.fromtimestamp(timestamp).ctime()

			return f"From {email} {ctime_date}\n".encode()

		for export_email in export_emails:
			from_line = mbox_from_line(export_email.sender, export_email.received_at)
			for mailbox_id in export_email.mailbox_ids:
				mbox_path = os.path.join(output_directory, f"{mailbox_map[mailbox_id]}.mbox")

				with open(mbox_path, "ab") as f:
					f.write(from_line)
					f.write(export_email.raw)

					if not export_email.raw.endswith(b"\n"):
						f.write(b"\n")

	@staticmethod
	def _write_maildir(export_emails: list[ExportEmail], output_directory: str) -> None:
		"""Writes the exported emails in Maildir format."""

		for subdir in ("tmp", "new", "cur"):
			os.makedirs(os.path.join(output_directory, subdir), exist_ok=True)

		for email in export_emails:
			flags = "".join(
				sorted(MailWriter.FLAG_MAP[k] for k in email.keywords if k in MailWriter.FLAG_MAP)
			)
			target_dir = "cur" if "$seen" in email.keywords else "new"

			if target_dir == "cur":
				filename = f"{uuid7()!s}:2,{flags}"
			else:
				filename = str(uuid7())

			path = os.path.join(output_directory, target_dir, filename)
			with open(path, "wb") as f:
				f.write(email.raw)

	@staticmethod
	def _write_maildir_nested(
		export_emails: list[ExportEmail], output_directory: str, mailbox_map: dict[str, str]
	) -> None:
		"""Writes the exported emails in Nested Maildir format."""

		for email in export_emails:
			flags = "".join(
				sorted(MailWriter.FLAG_MAP[k] for k in email.keywords if k in MailWriter.FLAG_MAP)
			)
			target_subdir = "cur" if "$seen" in email.keywords else "new"

			for mailbox_id in email.mailbox_ids:
				folder_safe = mailbox_map[mailbox_id].replace(" ", "_").replace("/", ".")
				maildir_path = os.path.join(output_directory, f".{folder_safe}")

				for sub in ("tmp", "new", "cur"):
					os.makedirs(os.path.join(maildir_path, sub), exist_ok=True)

				if target_subdir == "cur":
					filename = f"{uuid7()!s}:2,{flags}"
				else:
					filename = str(uuid7())

				path = os.path.join(maildir_path, target_subdir, filename)
				with open(path, "wb") as f:
					f.write(email.raw)


class MailExchange(Document):
	@property
	def _export_filter(self) -> dict:
		"""Returns the export filter as a dictionary."""

		if self.operation == "Export" and self.export_filter:
			return json.loads(self.export_filter)
		return {}

	@property
	def _export_sort(self) -> list[dict]:
		"""Returns the export sort as a list of dictionaries."""

		if self.operation == "Export":
			if self.export_sort == "Received At (ASC)":
				return [{"property": "receivedAt", "isAscending": True}]
			elif self.export_sort == "Received At (DESC)":
				return [{"property": "receivedAt", "isAscending": False}]

		return []

	@property
	def _metadata(self) -> dict:
		"""Returns the import metadata as a dictionary."""

		if self.operation != "Import" or self.import_format != "eml":
			return {}

		return json.loads(self.import_metadata or "{}")

	@property
	def max_import(self) -> int:
		return cint(frappe.conf.mail_exchange_max_import) or 1_000

	@property
	def max_export(self) -> int:
		return cint(frappe.conf.mail_exchange_max_export) or 1_000

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		if self.is_new():
			self.validate_user()
			self.validate_tenant()
		if self.operation == "Import":
			self.validate_import_format()
			self.validate_import_file()
			self.validate_import_metadata()
		elif self.operation == "Export":
			self.validate_export_filter()
			self.validate_export_sort()
			self.validate_export_limit()
			self.validate_export_archive_type()

	def before_submit(self) -> None:
		self.status = "Queued"
		self.queued_at = now()

	def on_submit(self) -> None:
		self.process()

	def before_cancel(self) -> None:
		self.status = "Cancelled"

	def validate_user(self) -> None:
		"""Validate the user."""

		if not has_role(self.user, "Mail User"):
			frappe.throw(_("User must have the 'Mail User' role."))

	def validate_tenant(self) -> None:
		"""Validate the tenant."""

		self.tenant = get_tenant_for_user(self.user)

	def validate_import_format(self) -> None:
		"""Validate the import format."""

		if not self.import_format:
			frappe.throw(_("Import Format is required."))

	def validate_import_file(self) -> None:
		"""Validate the import file."""

		if not self.import_file:
			frappe.throw(_("Import File is required."))

		allowed_extensions = [".eml", ".zip", ".tgz", ".tar.gz"]
		if not self.import_file.endswith(tuple(allowed_extensions)):
			frappe.throw(
				_("Only {0} files are supported for import.").format(
					", ".join(f"<code>{ext}</code>" for ext in allowed_extensions)
				)
			)

	def validate_import_metadata(self) -> None:
		"""Validate the import metadata."""

		if self.import_format == "eml":
			metadata = self._metadata
			if not metadata.get("mailboxIds"):
				frappe.throw(_("mailboxIds are required in Metadata for EML format."))
		else:
			self.import_metadata = json.dumps({})

	def validate_export_filter(self) -> None:
		"""Validate the export filter."""

		if self.export_filter:
			try:
				export_filter = json.loads(self.export_filter)
				self.export_filter = json.dumps(export_filter, indent=4)
			except json.JSONDecodeError:
				frappe.throw(_("Filter must be a valid JSON."))

	def validate_export_sort(self) -> None:
		"""Validate the export sort."""

		if not self.export_limit or not self.export_sort:
			self.export_sort = "Received At (ASC)"

	def validate_export_limit(self) -> None:
		"""Validate the export limit."""

		if cint(self.export_limit) > self.max_export:
			frappe.throw(_("Export Limit cannot exceed {0}.").format(self.max_export))

	def validate_export_archive_type(self) -> None:
		"""Validate the export archive type."""

		if not self.export_archive_type:
			frappe.throw(_("Archive Type is required."))

	def process(self) -> None:
		"""Enqueue the import or export based on the operation type."""

		if self.operation == "Import":
			job_id = f"{self.name}:mail:import"
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"_import",
				queue="long",
				timeout=cint(frappe.conf.mail_exchange_import_timeout) or 3600,
				job_id=job_id,
				deduplicate=True,
				enqueue_after_commit=True,
			)
		elif self.operation == "Export":
			job_id = f"{self.name}:mail:export"
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"_export",
				queue="long",
				timeout=cint(frappe.conf.mail_exchange_export_timeout) or 3600,
				job_id=job_id,
				deduplicate=True,
				enqueue_after_commit=True,
			)

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retry the import or export."""

		frappe.only_for("System Manager")

		if self.docstatus != 1:
			frappe.throw(_("Only submitted mail exchange can be retried."))
		elif self.status not in ["Queued", "In Progress", "Failed"]:
			frappe.throw(
				_("Only mail exchange with status 'Queued', 'In Progress', or 'Failed' can be retried.")
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

	def _import(self) -> None:
		"""Imports the mail data."""

		if self.operation != "Import":
			return

		freeze_jmap_push_notifications(self.user)
		self._mark_started()

		import_file = os.path.join(get_bench_path(), f"sites/{frappe.local.site}{self.import_file}")
		import_base = os.path.join(get_mail_import_directory(), self.name)
		os.makedirs(import_base, exist_ok=True)

		kwargs = {}
		try:
			output = ""

			if self.import_format == "eml" and self.import_file.endswith(".eml"):
				output += _("Copying EML file to import directory...{0}").format("\n")
				shutil.copy(import_file, os.path.join(import_base, os.path.basename(import_file)))
			else:
				output += _("Extracting import file...{0}").format("\n")
				extract_compressed_file(import_file, import_base)

			output += _("Connecting to JMAP server...{0}").format("\n")
			client = get_jmap_client(self.user)
			batch_size = client.max_objects_in_set

			mailbox_map = {}
			if self.import_format == "mbox":
				mailbox_map = {m["id"]: m["_name"] for m in client.mailboxes}
				mailbox_names = set(mailbox_map.values())
				for mbox_path in get_mbox_files(import_base):
					mailbox_name = os.path.basename(mbox_path).rsplit(".", 1)[0]
					if mailbox_name not in mailbox_names:
						output += _("Creating mailbox '{0}'...{1}").format(mailbox_name, "\n")
						mailbox = frappe.new_doc("Mailbox")
						mailbox.user = self.user
						mailbox._name = mailbox_name
						mailbox.insert()
						mailbox_map[mailbox.id] = mailbox._name

			metadata = MetadataLoader.load(self.import_format, import_base, mailbox_map, self._metadata)
			if not metadata:
				frappe.throw(_("No emails found in the import file."))

			if len(metadata) > self.max_import:
				frappe.throw(_("Email count for import cannot exceed {0}.").format(self.max_import))

			output += _("Uploading email blobs in batches of {0}...{1}").format(batch_size, "\n")
			for idx, meta_batch in enumerate(create_batch(metadata, batch_size)):
				output += _("{0}Processing batch {1}...{2}").format("\t", idx + 1, "\n")

				output += _("{0}Loading blobs...{1}").format("\t\t", "\n")
				blobs: list[tuple[bytes, str]] = []
				for meta in meta_batch:
					with open(os.path.join(import_base, meta.blob_path), "rb") as f:
						blobs.append((f.read(), "message/rfc822"))

				responses = client.upload_blobs_concurrently(blobs)
				if not responses:
					frappe.throw(_("No blobs uploaded in batch {0}.").format(idx + 1))

				emails = {}
				for i, resp in enumerate(responses):
					new_blob_id = resp["blobId"]
					meta = meta_batch[i]
					email = {
						"blobId": new_blob_id,
						"mailboxIds": {mb_id: True for mb_id in meta.mailbox_ids},
						"keywords": {kw: True for kw in meta.keywords} if meta.keywords else {},
						"receivedAt": meta.received_at.isoformat() if meta.received_at else None,
					}
					emails[f"e{i+1}"] = email

				response = client._make_request(
					using=["urn:ietf:params:jmap:mail"],
					method_calls=[
						[
							"Email/import",
							{
								"accountId": client.primary_account_id,
								"emails": emails,
							},
							"0",
						]
					],
				)
				result = response["methodResponses"][0][1]

				if created := result.get("created", {}):
					output += _("{0}Created {1} emails.{2}").format("\t\t", len(created), "\n")
				if failed := result.get("notCreated", {}):
					output += _("{0}Failed to create {1} emails.{2}").format("\t\t", len(failed), "\n")

			clear_sync_state(self.user, type="email")
			kwargs.update({"status": "Completed", "output": output})

			mail_details = {
				"subject": _("Mail Data Import Completed"),
				"title": _("Mail data import for account {0} has been completed successfully.").format(
					frappe.bold(get_account_for_user(self.user))
				),
				"description": _("Click the button below to view the imported data."),
			}

		except Exception as e:
			kwargs.update({"status": "Failed", "output": str(e)})

			mail_details = {
				"subject": _("Mail Data Import Failed"),
				"title": _("Mail data import for account {0} has failed.").format(
					frappe.bold(get_account_for_user(self.user))
				),
				"description": _("Click the button below to view the reason for failure."),
			}

		shutil.rmtree(import_base, ignore_errors=True)
		self._mark_completed(**kwargs)
		unfreeze_jmap_push_notifications(self.user)

		if not is_administrator(self.owner):
			if email := get_user_email_address(self.owner):
				frappe.sendmail(
					recipients=email,
					subject=mail_details["subject"],
					template="generic",
					args={
						"title": mail_details["title"],
						"description": mail_details["description"],
						"button": _("View Import"),
						"link": get_url(f"/mail/mail-exchanges/{self.name}"),
					},
					now=True,
				)

	def _export(self) -> None:
		"""Exports the mail data."""

		if self.operation != "Export":
			return

		self._mark_started()
		output_dir = os.path.join(get_mail_export_directory(), self.name)
		os.makedirs(output_dir, exist_ok=True)

		output_file_name = f"{self.name}{self.export_archive_type}"
		output_file_url = f"/private/files/{output_file_name}"
		output_file = os.path.join(get_bench_path(), f"sites/{frappe.local.site}{output_file_url}")

		kwargs = {}
		try:
			output = ""

			output += _("Connecting to JMAP server...{0}").format("\n")
			self._publish_progress(0, 100, _("Connecting to JMAP server"))
			client = get_jmap_client(self.user)

			output += _("Counting emails to export...{0}").format("\n")
			total = client.email_query(self._export_filter, limit=1)["total"]
			limit = min(total, cint(self.export_limit)) if self.export_limit else total

			max_export = self.max_export
			if limit > max_export:
				if not self.export_limit:
					frappe.throw(
						_("Email count for export cannot exceed {0}. Please set an Export Limit.").format(
							max_export
						)
					)

				frappe.throw(_("Email count for export cannot exceed {0}.").format(max_export))

			output += _("Fetching email IDs...{0}").format("\n")
			self._publish_progress(10, 100, _("Fetching email IDs"))
			ids = client.email_query(self._export_filter, sort=self._export_sort, limit=limit)["ids"]

			if not ids:
				raise Exception(_("No emails found for the given filter."))

			output += _("Fetching email metadata...{0}").format("\n")
			self._publish_progress(30, 100, _("Fetching email metadata"))
			properties = ["id", "from", "blobId", "keywords", "mailboxIds", "messageId", "receivedAt"]
			emails, _state = client.email_get(ids, properties=properties)

			if not emails:
				raise Exception(_("Failed to fetch email metadata."))

			if self.deduplicate_export:
				output += _("Deduplicating emails based on Message-ID...{0}").format("\n")
				self._publish_progress(50, 100, _("Deduplicating emails"))
				unique_emails = {}
				for email in emails:
					key = email["messageId"][0]
					if key not in unique_emails:
						unique_emails[key] = email
				emails = list(unique_emails.values())

			mailbox_map = {}
			if self.export_format == "jmap":
				output += _("Saving email metadata...{0}").format("\n")
				self._publish_progress(70, 100, _("Saving email metadata"))
				MailWriter.write_metadata(emails, output_dir)
			elif self.export_format in ["mbox", "maildir-nested"]:
				output += _("Fetching mailboxes...{0}").format("\n")
				mailbox_map = {m["id"]: m["_name"] for m in client.mailboxes}

			batch_size = cint(frappe.conf.mail_exchange_export_batch_size) or 500
			output += _("Downloading email blobs in batches of {0}...{1}").format(batch_size, "\n")
			for idx, emails_batch in enumerate(create_batch(emails, batch_size)):
				output += _("{0}Processing batch {1}...{2}").format("\t", idx + 1, "\n")
				self._publish_progress(
					70 + ((idx + 1) / (len(ids) / batch_size)) * 30,
					100,
					_("Downloading email blobs {0}/{1}").format((idx + 1) * batch_size, len(ids)),
				)

				blobs = []
				for email in emails_batch:
					if not email["blobId"]:
						output += _("{0}Skipping email {1} as it has no blobId.{3}").format(
							"\t\t", email["id"], "\n"
						)
						continue
					blobs.append((email["blobId"], None))

				if not blobs:
					continue

				downloaded_blobs = client.download_blobs_concurrently(blobs)
				if not downloaded_blobs:
					output += _("{0}Failed to download blobs for batch {1}.{2}").format("\t\t", idx + 1, "\n")
					continue

				output += _("{0}Saving exported emails...{1}").format("\t\t", "\n")
				export_emails: list[ExportEmail] = []
				for email in emails_batch:
					blob_id = email["blobId"]
					if blob_id not in downloaded_blobs:
						continue

					sender = email["from"][0] if email.get("from") else {}
					export_email = ExportEmail(
						id=email["id"],
						sender=sender,
						blob_id=blob_id,
						mailbox_ids=set(email["mailboxIds"].keys()),
						keywords=set(email["keywords"].keys()),
						received_at=datetime.fromisoformat(email["receivedAt"]),
						message_id=email["messageId"][0],
						raw=downloaded_blobs[blob_id],
					)
					export_emails.append(export_email)

				MailWriter.write(self.export_format, export_emails, output_dir, mailbox_map)

			output += _("Creating archive...{0}").format("\n")
			self._publish_progress(95, 100, _("Creating archive"))
			compress_directory(output_dir, output_file)

			output += _("Attaching export file to Mail Exchange document...{0}").format("\n")
			file = frappe.new_doc("File")
			file.is_private = 1
			file.file_url = output_file_url
			file.file_name = output_file_name
			file.attached_to_doctype = self.doctype
			file.attached_to_name = self.name
			file.attached_to_field = "file"
			file.insert()

			# https://github.com/frappe/frappe/issues/26615
			frappe.db.set_value(
				"File", file.name, {"file_url": output_file_url, "file_name": output_file_name}
			)

			kwargs.update({"status": "Completed", "output": output.strip()})

			mail_details = {
				"subject": _("Mail Data Export Ready"),
				"title": _("Mail data export for account {0} is ready for download.").format(
					frappe.bold(get_account_for_user(self.user))
				),
				"description": _("Click the button below to view and download the exported data."),
			}

		except Exception as e:
			kwargs.update({"status": "Failed", "output": str(e)})

			mail_details = {
				"subject": _("Mail Data Export Failed"),
				"title": _("Mail data export for account {0} has failed.").format(
					frappe.bold(get_account_for_user(self.user))
				),
				"description": _("Click the button below to view the reason for failure."),
			}

		shutil.rmtree(output_dir, ignore_errors=True)
		self._mark_completed(**kwargs)

		if not is_administrator(self.owner):
			if email := get_user_email_address(self.owner):
				frappe.sendmail(
					recipients=email,
					subject=mail_details["subject"],
					template="generic",
					args={
						"title": mail_details["title"],
						"description": mail_details["description"],
						"button": _("View Export"),
						"link": get_url(f"/mail/mail-exchanges/{self.name}"),
					},
					now=True,
				)

	def _mark_started(self) -> None:
		"""Marks the mail exchange as started and updates the started_at and started_after fields."""

		started_at = now()
		started_after = time_diff_in_seconds(started_at, self.queued_at)
		self._db_set(
			status="In Progress", started_at=started_at, started_after=started_after, notify=True, commit=True
		)

	def _mark_completed(self, **kwargs) -> None:
		"""Marks the mail exchange as completed and updates the completed_at and duration fields."""

		kwargs["completed_at"] = now()
		kwargs["duration"] = time_diff_in_seconds(kwargs["completed_at"], self.started_at)

		if kwargs["status"] == "Failed":
			kwargs["retries"] = cint(self.retries) + 1

		self._db_set(notify=True, **kwargs)

	def _publish_progress(self, progress: int, total: int, msg: str = "") -> None:
		"""Publish the exchange progress to the user via real-time updates."""

		title = _("Mail Exchange Progress")
		frappe.publish_realtime(
			"mail_exchange_progress",
			{
				"exchange": self.name,
				"progress": (progress / total) * 100,
				"title": title,
				"msg": msg or title,
			},
			doctype=self.doctype,
			docname=self.name,
			user=frappe.session.user,
		)

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
			return f"(`tabMail Exchange`.tenant = '{tenant}')"

	if has_role(user, "Mail User"):
		return f"(`tabMail Exchange`.user = '{user}')"

	return "1=0"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Exchange":
		return False

	user = user or frappe.session.user

	if is_system_manager(user):
		return True
	elif has_role(user, "Mail Admin"):
		return is_tenant_admin(doc.tenant, user)
	elif has_role(user, "Mail User"):
		return doc.user == user

	return False


def retry_stuck_mail_exchanges() -> None:
	"""Called by the scheduler to retry stuck mail exchanges."""

	ME = frappe.qb.DocType("Mail Exchange")
	exchanges = (
		frappe.qb.from_(ME)
		.select(ME.name)
		.where(
			(ME.status.isin(["Queued", "In Progress"]))
			& (ME.queued_at <= get_datetime(add_to_date(now(), hours=-1)))
		)
		.orderby(ME.queued_at, order=Order.asc)
	).run(pluck="name")

	if not exchanges:
		return

	for exchange in exchanges:
		doc = frappe.get_doc("Mail Exchange", exchange)
		doc.retry()


def clean_import_export_directories() -> None:
	"""Called by the scheduler to clean up import and export directories."""

	for directory in (get_mail_import_directory(), get_mail_export_directory()):
		if os.path.exists(directory):
			for item in os.listdir(directory):
				item_path = os.path.join(directory, item)
				if os.path.isdir(item_path):
					if frappe.db.exists("Mail Exchange", {"name": item, "status": "In Progress"}):
						continue

					shutil.rmtree(item_path, ignore_errors=True)
				else:
					os.remove(item_path)
