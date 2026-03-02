# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import mailbox
import os
import shutil
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import uuid7

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

from mail.client.doctype.push_subscription.push_subscription import (
	freeze_jmap_push_notifications,
	unfreeze_jmap_push_notifications,
)
from mail.jmap import JMAPClient, get_jmap_client
from mail.utils import (
	compress_directory,
	extract_compressed_file,
	get_mail_export_directory,
	get_mail_import_directory,
	get_mbox_files,
	reconnect_on_failure,
)
from mail.utils.cache import get_tenant_for_user
from mail.utils.user import (
	clear_sync_state,
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

MAILDIR_FLAG_MAP: dict[str, str] = {
	"$seen": "S",
	"$flagged": "F",
	"$answered": "R",
	"$draft": "D",
}


@dataclass(slots=True)
class ImportEmailMeta:
	blob_path: str
	mailbox_ids: set[str]
	keywords: set[str]


@dataclass(slots=True)
class ExportEmail:
	id: str
	sender: dict[str, str]
	blob_id: str
	keywords: set[str]
	mailbox_ids: set[str]
	message_id: str
	received_at: datetime
	raw: bytes


class ImportMetadataLoader:
	@classmethod
	def load(
		cls,
		format: Literal["eml", "jmap", "mbox", "maildir", "maildir-nested"],
		base_dir: str,
		mailbox_map: dict[str, str],
		metadata: dict,
	) -> list[ImportEmailMeta]:
		"""Loads import metadata based on the specified format."""

		loaders = {
			"eml": cls._from_eml,
			"jmap": cls._from_jmap,
			"mbox": cls._from_mbox,
			"maildir": cls._from_maildir,
			"maildir-nested": cls._from_nested_maildir,
		}

		if format not in loaders:
			frappe.throw(_("Unsupported import format: {0}").format(format))

		return loaders[format](base_dir, mailbox_map, metadata)

	@staticmethod
	def _load_json_metadata(base_dir: str) -> list[str]:
		"""Loads email metadata from emails.json file."""

		path = os.path.join(base_dir, "emails.json")
		if not os.path.exists(path):
			frappe.throw(_("emails.json not found in the import directory."))

		with open(path) as f:
			return json.load(f)

	@staticmethod
	def _from_eml(base_dir: str, mailbox_map: dict[str, str], metadata: dict) -> list[ImportEmailMeta]:
		"""Loads import metadata for EML format."""

		mailbox_ids = set(metadata.get("mailboxIds", {}).keys())
		if not mailbox_ids:
			frappe.throw(_("mailboxIds are required in Metadata for EML format."))

		keywords = set(metadata.get("keywords", {}).keys() or [])

		files = [f for f in os.listdir(base_dir) if f.lower().endswith(".eml")]
		if not files:
			frappe.throw(_("No .eml files found"))

		return [ImportEmailMeta(f, mailbox_ids, keywords) for f in files]

	@classmethod
	def _from_jmap(cls, base_dir: str, *args, **kwargs) -> list[ImportEmailMeta]:
		"""Loads import metadata for JMAP format."""

		validate_jmap_structure(base_dir, ["emails.json"], raise_exception=True)

		result: list[ImportEmailMeta] = []
		for meta in cls._load_json_metadata(base_dir):
			result.append(
				ImportEmailMeta(
					blob_path=os.path.join("blobs", meta["blobId"]),
					mailbox_ids=set(meta["mailboxIds"].keys()),
					keywords=set(meta.get("keywords", {}).keys() or []),
				)
			)

		return result

	@staticmethod
	def _from_mbox(base_dir: str, mailbox_map: dict[str, str], *args, **kwargs) -> list[ImportEmailMeta]:
		"""Loads import metadata for MBOX format."""

		mbox_files = get_mbox_files(base_dir)
		if not mbox_files:
			frappe.throw(_("No .mbox files found"))

		by_message_id: dict[str, ImportEmailMeta] = {}
		for mbox_path in mbox_files:
			mailbox_id = next(
				(k for k, v in mailbox_map.items() if f"{v}.mbox" == os.path.basename(mbox_path)),
				None,
			)
			if not mailbox_id:
				frappe.throw(_("Mailbox not found for {0}").format(mbox_path))

			with closing(mailbox.mbox(mbox_path, factory=None)) as mbox:
				for key, msg in mbox.items():
					msg_id = msg.get("Message-ID") or key

					if msg_id in by_message_id:
						by_message_id[msg_id].mailbox_ids.add(mailbox_id)
						continue

					blob = f"{uuid7()}.eml"
					with open(os.path.join(base_dir, blob), "wb") as f:
						f.write(msg.as_bytes(unixfrom=True))

					by_message_id[msg_id] = ImportEmailMeta(
						blob_path=blob,
						mailbox_ids={mailbox_id},
						keywords=set(),
					)

		return list(by_message_id.values())

	@staticmethod
	def _parse_maildir_flags(filename: str, seen_by_default: bool) -> set[str]:
		"""Parses Maildir flags from the filename and returns the corresponding keywords."""

		reverse_map = {v: k for k, v in MAILDIR_FLAG_MAP.items()}
		keywords: set[str] = set()

		if seen_by_default:
			keywords.add("$seen")

		if ":2," not in filename:
			return keywords

		flags = filename.split(":2,", 1)[1]
		for f in flags:
			if kw := reverse_map.get(f):
				keywords.add(kw)

		if "S" not in flags:
			keywords.discard("$seen")

		return keywords

	@classmethod
	def _from_maildir(
		cls, base_dir: str, mailbox_map: dict[str, str], metadata: dict
	) -> list[ImportEmailMeta]:
		"""Loads import metadata for Maildir format."""

		validate_maildir_or_maildirpp(base_dir, raise_exception=True)
		mailbox_ids = set(metadata.get("mailboxIds", {}).keys())
		if not mailbox_ids:
			frappe.throw(_("mailboxIds are required in Metadata for Maildir format."))

		result: list[ImportEmailMeta] = []
		for subdir in ("cur", "new"):
			path = os.path.join(base_dir, subdir)
			if not os.path.isdir(path):
				continue

			for fname in os.listdir(path):
				keywords = cls._parse_maildir_flags(fname, subdir == "cur")
				result.append(
					ImportEmailMeta(
						blob_path=os.path.join(subdir, fname),
						mailbox_ids=mailbox_ids,
						keywords=keywords,
					)
				)

		return result

	@classmethod
	def _from_nested_maildir(
		cls, base_dir: str, mailbox_map: dict[str, str], metadata: dict
	) -> list[ImportEmailMeta]:
		"""Loads import metadata for Nested Maildir format."""

		validate_nested_maildir_tree(base_dir, raise_exception=True)
		result: list[ImportEmailMeta] = []

		path_to_id = {v: k for k, v in mailbox_map.items()}

		def resolve_mailbox_path(dir_path: str) -> str:
			"""Resolves the mailbox path from the directory path."""

			rel = os.path.relpath(dir_path, base_dir)
			if rel == ".":
				return ""

			parts = []
			for part in rel.split(os.sep):
				if not part.startswith("."):
					continue
				parts.append(part[1:].replace("_", " "))

			return "/".join(parts)

		for root, dirs, _files in os.walk(base_dir):
			if not {"cur", "new"} & set(dirs):
				continue

			mailbox_path = resolve_mailbox_path(root)
			if not mailbox_path:
				continue

			mailbox_id = path_to_id.get(mailbox_path)
			if not mailbox_id:
				frappe.throw(_("Mailbox not found for folder {0}").format(mailbox_path))

			for subdir in ("cur", "new"):
				path = os.path.join(root, subdir)
				if not os.path.isdir(path):
					continue

				for fname in os.listdir(path):
					if fname.startswith("."):
						continue

					keywords = cls._parse_maildir_flags(fname, subdir == "cur")
					rel_blob = os.path.relpath(os.path.join(path, fname), base_dir)
					result.append(ImportEmailMeta(rel_blob, {mailbox_id}, keywords))

		return result


class ExportWriter:
	@classmethod
	def write(
		cls,
		format: Literal["jmap", "mbox", "maildir", "maildir-nested"],
		emails: list[ExportEmail],
		out_dir: str,
		mailbox_map: dict[str, str],
	) -> None:
		"""Writes the exported emails in the specified format."""

		writers = {
			"jmap": cls._jmap,
			"mbox": cls._mbox,
			"maildir": cls._maildir,
			"maildir-nested": cls._maildir_nested,
		}

		if format not in writers:
			frappe.throw(_("Unsupported export format: {0}").format(format))

		writers[format](emails, out_dir, mailbox_map)

	@staticmethod
	def write_meta(metadata: list[dict], out_dir: str) -> None:
		"""Writes the exported email metadata in emails.json file."""

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

		with open(os.path.join(out_dir, "emails.json"), "w") as f:
			json.dump(_metadata, f, indent=4)

	@staticmethod
	def _jmap(emails: list[ExportEmail], out_dir: str, *args, **kwargs) -> None:
		"""Writes the exported emails in JMAP format."""

		blobs = os.path.join(out_dir, "blobs")
		os.makedirs(blobs, exist_ok=True)
		for e in emails:
			with open(os.path.join(blobs, e.blob_id), "wb") as f:
				f.write(e.raw)

	@staticmethod
	def _mbox(emails: list[ExportEmail], out_dir: str, mailbox_map: dict[str, str]) -> None:
		"""Writes the exported emails in MBOX format."""

		def from_line(sender: dict[str, str], received_at: datetime) -> bytes:
			"""Generates the From line for MBOX format."""

			addr = sender.get("email", "unknown")
			return f"From {addr} {received_at.ctime()}\n".encode()

		for e in emails:
			line = from_line(e.sender, e.received_at)
			for m_id in e.mailbox_ids:
				path = os.path.join(out_dir, f"{mailbox_map[m_id]}.mbox")
				with open(path, "ab") as f:
					f.write(line)
					f.write(e.raw)
					if not e.raw.endswith(b"\n"):
						f.write(b"\n")

	@staticmethod
	def _maildir(emails: list[ExportEmail], out_dir: str, *args, **kwargs) -> None:
		"""Writes the exported emails in Maildir format."""

		for dir in ("tmp", "new", "cur"):
			os.makedirs(os.path.join(out_dir, dir), exist_ok=True)

		for e in emails:
			flags = "".join(sorted(MAILDIR_FLAG_MAP[k] for k in e.keywords if k in MAILDIR_FLAG_MAP))
			target = "cur" if "$seen" in e.keywords else "new"
			name = f"{uuid7()}:2,{flags}" if target == "cur" else str(uuid7())
			with open(os.path.join(out_dir, target, name), "wb") as f:
				f.write(e.raw)

	@staticmethod
	def _maildir_nested(emails: list[ExportEmail], out_dir: str, mailbox_map: dict[str, str]) -> None:
		"""Writes the exported emails in Nested Maildir format."""

		def mailbox_to_root(mailbox_name: str) -> str:
			"""Converts mailbox name to nested Maildir root path."""

			parts = mailbox_name.split("/")
			path = out_dir

			for part in parts:
				safe = part.replace(" ", "_")
				path = os.path.join(path, f".{safe}")

			return path

		for e in emails:
			flags = "".join(sorted(MAILDIR_FLAG_MAP[k] for k in e.keywords if k in MAILDIR_FLAG_MAP))
			target = "cur" if "$seen" in e.keywords else "new"

			for m_id in e.mailbox_ids:
				mailbox_name = mailbox_map[m_id]
				maildir_root = mailbox_to_root(mailbox_name)

				for d in ("new", "cur"):
					os.makedirs(os.path.join(maildir_root, d), exist_ok=True)

				filename = f"{uuid7()}:2,{flags}" if target == "cur" else str(uuid7())
				with open(os.path.join(maildir_root, target, filename), "wb") as f:
					f.write(e.raw)


class MailExchange(Document):
	@property
	def max_import(self) -> int:
		"""Returns the maximum number of emails allowed for import."""

		return cint(frappe.conf.mail_exchange_max_import) or 1_000

	@property
	def max_export(self) -> int:
		"""Returns the maximum number of emails allowed for export."""

		return cint(frappe.conf.mail_exchange_max_export) or 1_000

	@property
	def export_filter_dict(self) -> dict:
		"""Returns the export filter as a dictionary."""

		if self.operation == "Export" and self.export_filter:
			return json.loads(self.export_filter)
		return {}

	@property
	def export_sort_clause(self) -> list[dict]:
		"""Returns the export sort as a list of dictionaries."""

		if self.operation != "Export":
			return []
		if self.export_sort == "Received At (DESC)":
			return [{"property": "receivedAt", "isAscending": False}]
		return [{"property": "receivedAt", "isAscending": True}]

	@property
	def import_metadata_dict(self) -> dict:
		"""Returns the import metadata as a dictionary."""

		if self.operation != "Import":
			return {}

		return json.loads(self.import_metadata or "{}")

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		if self.is_new():
			self.validate_user()
			self.validate_tenant()

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

		if not has_role(self.user, "Mail User"):
			frappe.throw(_("User must have the 'Mail User' role."))

	def validate_tenant(self) -> None:
		"""Validate the tenant."""

		self.tenant = get_tenant_for_user(self.user)

	def validate_import(self) -> None:
		"""Validate the import parameters."""

		if not self.import_format:
			frappe.throw(_("Import Format is required."))
		if not self.import_file:
			frappe.throw(_("Import File is required."))

		allowed_extensions = (".eml", ".zip", ".tgz", ".tar.gz")
		if not self.import_file.endswith(allowed_extensions):
			frappe.throw(
				_("Only {0} files are supported for import.").format(
					", ".join(f"<code>{ext}</code>" for ext in allowed_extensions)
				)
			)

		if self.import_format in ("eml", "maildir"):
			meta = self.import_metadata_dict
			if not meta.get("mailboxIds"):
				frappe.throw(_("mailboxIds are required in Metadata for EML and Maildir formats."))
		else:
			self.import_metadata = json.dumps({})

	def validate_export(self) -> None:
		"""Validate the export parameters."""

		if self.export_filter:
			if isinstance(self.export_filter, dict):
				self.export_filter = json.dumps(self.export_filter, indent=4)
			else:
				try:
					self.export_filter = json.dumps(json.loads(self.export_filter), indent=4)
				except json.JSONDecodeError:
					frappe.throw(_("Export filter must be valid JSON."))

		if not self.export_archive_type:
			frappe.throw(_("Archive Type is required."))

		if not self.export_sort:
			self.export_sort = "Received At (ASC)"

		if self.export_limit:
			export_limit = cint(self.export_limit)
			if export_limit <= 0:
				frappe.throw(_("Export Limit must be greater than zero."))
			if export_limit > self.max_export:
				frappe.throw(_("Export Limit cannot exceed {0}.").format(self.max_export))
			self.export_limit = export_limit
		else:
			self.export_limit = self.max_export

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

		self._db_set(status="Queued", queued_at=now())
		self.process()

	@reconnect_on_failure()
	def _import(self) -> None:
		"""Imports the mail data."""

		if self.operation != "Import":
			return

		freeze_jmap_push_notifications(self.user)
		self._mark_started()

		import_file = os.path.join(get_bench_path(), f"sites/{frappe.local.site}{self.import_file}")
		base_dir = os.path.join(get_mail_import_directory(), self.name)
		os.makedirs(base_dir, exist_ok=True)

		kwargs = {}
		try:
			if self.import_format == "eml" and self.import_file.endswith(".eml"):
				shutil.copy(import_file, os.path.join(base_dir, os.path.basename(import_file)))
			else:
				extract_compressed_file(import_file, base_dir)

			client = get_jmap_client(self.user)

			mailbox_map = {}
			if self.import_format == "mbox":
				mailbox_map = {m["id"]: m["_name"] for m in client.mailboxes}
			elif self.import_format == "maildir-nested":
				mailbox_map = self._build_mailbox_map(client.mailboxes)

			meta = ImportMetadataLoader.load(
				self.import_format, base_dir, mailbox_map, self.import_metadata_dict
			)

			if not meta:
				frappe.throw(_("No emails found for import."))
			if len(meta) > self.max_import:
				frappe.throw(_("Import limit exceeded."))

			self._import_batches(client, base_dir, meta)
			clear_sync_state(self.user, type="email")

			kwargs.update({"status": "Completed", "output": _("Import completed")})
		except Exception:
			kwargs.update({"status": "Failed", "output": frappe.get_traceback(with_context=False)})
		finally:
			shutil.rmtree(base_dir, ignore_errors=True)
			unfreeze_jmap_push_notifications(self.user)

		self._mark_completed(**kwargs)
		self._notify_user(success=kwargs.get("status") == "Completed", action="Import")

	@reconnect_on_failure()
	def _export(self) -> None:
		"""Exports the mail data."""

		if self.operation != "Export":
			return

		self._mark_started()
		out_dir = os.path.join(get_mail_export_directory(), self.name)
		os.makedirs(out_dir, exist_ok=True)

		kwargs = {}
		try:
			client = get_jmap_client(self.user)
			total = client.email_query(self.export_filter_dict, limit=1)["total"]
			limit = min(total, cint(self.export_limit or total))

			if limit > self.max_export:
				frappe.throw(_("Export limit exceeded."))

			ids = client.email_query(self.export_filter_dict, sort=self.export_sort_clause, limit=limit)[
				"ids"
			]
			if not ids:
				frappe.throw(_("No emails found for export."))

			properties = ["id", "from", "blobId", "keywords", "mailboxIds", "messageId", "receivedAt"]
			emails, _state = client.email_get(ids, properties=properties)

			if self.deduplicate_export:
				unique_emails = {}
				for e in emails:
					key = e["messageId"][0]
					if key not in unique_emails:
						unique_emails[key] = e
				emails = list(unique_emails.values())

			mailbox_map = {}
			if self.export_format == "mbox":
				mailbox_map = {m["id"]: m["_name"] for m in client.mailboxes}
			elif self.export_format == "maildir-nested":
				mailbox_map = self._build_mailbox_map(client.mailboxes)

			self._export_batches(client, emails, out_dir, mailbox_map)
			self._attach_export(out_dir)

			kwargs.update({"status": "Completed", "output": _("Export completed")})
		except Exception:
			kwargs.update({"status": "Failed", "output": frappe.get_traceback(with_context=False)})
		finally:
			shutil.rmtree(out_dir, ignore_errors=True)

		self._mark_completed(**kwargs)
		self._notify_user(success=kwargs.get("status") == "Completed", action="Export")

	def _mark_started(self) -> None:
		"""Marks the mail exchange as started and updates the started_at and started_after fields."""

		started_at = now()
		self._db_set(
			status="In Progress",
			started_at=started_at,
			started_after=time_diff_in_seconds(started_at, self.queued_at),
		)

	def _mark_completed(self, **kwargs) -> None:
		"""Marks the mail exchange as completed and updates the completed_at and duration fields."""

		kwargs["completed_at"] = now()
		kwargs["duration"] = time_diff_in_seconds(kwargs["completed_at"], self.started_at)

		if kwargs["status"] == "Failed":
			kwargs["retries"] = cint(self.retries) + 1

		self._db_set(**kwargs)

	def _import_batches(self, client: JMAPClient, base_dir: str, metadata: list[ImportEmailMeta]) -> None:
		"""Imports emails in batches using the JMAP client."""

		batch_size = client.max_objects_in_set
		for batch in create_batch(metadata, batch_size):
			blobs: list[tuple[bytes, str]] = []
			for meta in batch:
				with open(os.path.join(base_dir, meta.blob_path), "rb") as f:
					blobs.append((f.read(), "message/rfc822"))

			responses = client.upload_blobs_concurrently(blobs)
			emails = {}
			for i, resp in enumerate(responses):
				meta = batch[i]
				emails[f"e{i}"] = {
					"blobId": resp["blobId"],
					"mailboxIds": {mid: True for mid in meta.mailbox_ids},
					"keywords": {k: True for k in meta.keywords or []},
				}

			client._make_request(
				using=["urn:ietf:params:jmap:mail"],
				method_calls=[
					["Email/import", {"accountId": client.primary_account_id, "emails": emails}, "0"]
				],
			)

	def _export_batches(
		self, client: JMAPClient, emails: list[dict], out_dir: str, mailbox_map: dict[str, str]
	) -> None:
		"""Exports emails in batches using the JMAP client."""

		if self.export_format == "jmap":
			ExportWriter.write_meta(emails, out_dir)

		batch_size = cint(frappe.conf.mail_exchange_export_batch_size) or 500
		for batch in create_batch(emails, batch_size):
			blobs = [(e["blobId"], None) for e in batch if e.get("blobId")]
			data = client.download_blobs_concurrently(blobs)

			export_emails = []
			for e in batch:
				if e.get("blobId") not in data:
					continue

				export_emails.append(
					ExportEmail(
						id=e["id"],
						sender=(e.get("from") or [{}])[0],
						blob_id=e["blobId"],
						keywords=set(e["keywords"].keys()),
						mailbox_ids=set(e["mailboxIds"].keys()),
						message_id=e.get("messageId", [""])[0],
						received_at=datetime.fromisoformat(e["receivedAt"]),
						raw=data[e["blobId"]],
					)
				)

			ExportWriter.write(self.export_format, export_emails, out_dir, mailbox_map)

	def _build_mailbox_map(self, mailboxes: list[dict]) -> dict[str, str]:
		"""Builds a mapping of mailbox IDs to their full paths."""

		by_id = {m["id"]: m for m in mailboxes}
		result: dict[str, str] = {}

		def resolve_path(mailbox_id: str) -> str:
			if mailbox_id in result:
				return result[mailbox_id]

			mailbox = by_id[mailbox_id]
			name = mailbox["_name"]
			parent_id = mailbox.get("parent_id")

			if parent_id:
				parent_path = resolve_path(parent_id)
				path = f"{parent_path}/{name}"
			else:
				path = name

			result[mailbox_id] = path
			return path

		for mailbox_id in by_id:
			resolve_path(mailbox_id)

		return result

	def _attach_export(self, out_dir: str) -> None:
		"""Attaches the exported file to the mail exchange."""

		archive = f"{self.name}{self.export_archive_type}"
		url = f"/private/files/{archive}"
		path = os.path.join(get_bench_path(), f"sites/{frappe.local.site}{url}")
		compress_directory(out_dir, path)

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

	def _notify_user(self, success: bool, action: Literal["Import", "Export"]) -> None:
		"""Sends notification email to the owner of the mail exchange."""

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
				"link": get_url(f"/mail/mail-exchanges/{self.name}"),
			},
			now=True,
		)

	def _db_set(self, **kwargs) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, notify=True, commit=True)


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

	for exchange in exchanges:
		frappe.get_doc("Mail Exchange", exchange).retry()


def clean_import_export_directories() -> None:
	"""Called by the scheduler to clean up import and export directories."""

	for base in (get_mail_import_directory(), get_mail_export_directory()):
		if not os.path.exists(base):
			continue

		for item in os.listdir(base):
			path = os.path.join(base, item)
			if os.path.isdir(path):
				if frappe.db.exists("Mail Exchange", {"name": item, "status": "In Progress"}):
					continue
				shutil.rmtree(path, ignore_errors=True)
			else:
				os.remove(path)
