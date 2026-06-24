# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import os
import shutil
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid7
from zoneinfo import ZoneInfo

import frappe
import isodate
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
	random_string,
	time_diff_in_seconds,
)

from mail.client.doctype.push_subscription.push_subscription import (
	freeze_jmap_push_notifications,
	unfreeze_jmap_push_notifications,
)
from mail.jmap import get_jmap_connection
from mail.jmap.services.calendars.calendar import CalendarService
from mail.jmap.services.calendars.calendar_event import CalendarEventService
from mail.utils import (
	compress_directory,
	extract_compressed_file,
	get_calendar_export_directory,
	get_calendar_import_directory,
	get_config,
	reconnect_on_failure,
)
from mail.utils.logger import ExchangeLogger, get_exchange_logger
from mail.utils.user import (
	get_user_email_address,
	is_administrator,
	is_jmap_configured,
	is_mail_admin,
	is_system_manager,
)

# JSCalendar (RFC 8984) -> iCalendar (RFC 5545) value maps.
STATUS_MAP: dict[str, str] = {
	"confirmed": "CONFIRMED",
	"tentative": "TENTATIVE",
	"cancelled": "CANCELLED",
}
PRIVACY_MAP: dict[str, str] = {
	"public": "PUBLIC",
	"private": "PRIVATE",
	"secret": "CONFIDENTIAL",
}
FREE_BUSY_MAP: dict[str, str] = {
	"free": "TRANSPARENT",
	"busy": "OPAQUE",
}
PARTICIPANT_ROLE_MAP: dict[str, str] = {
	"chair": "CHAIR",
	"required": "REQ-PARTICIPANT",
	"attendee": "REQ-PARTICIPANT",
	"optional": "OPT-PARTICIPANT",
	"informational": "NON-PARTICIPANT",
}
PARTSTAT_MAP: dict[str, str] = {
	"needs-action": "NEEDS-ACTION",
	"accepted": "ACCEPTED",
	"declined": "DECLINED",
	"tentative": "TENTATIVE",
	"delegated": "DELEGATED",
}
CUTYPE_MAP: dict[str, str] = {
	"individual": "INDIVIDUAL",
	"group": "GROUP",
	"resource": "RESOURCE",
	"location": "ROOM",
}
WEEKDAY_MAP: dict[str, str] = {
	"mo": "MO",
	"tu": "TU",
	"we": "WE",
	"th": "TH",
	"fr": "FR",
	"sa": "SA",
	"su": "SU",
}

# Server-managed / computed properties that must be dropped before re-creating an event,
# otherwise the JMAP server rejects the "set" call with invalidProperties.
SERVER_MANAGED_KEYS = (
	"id",
	"blobId",
	"method",
	"x-href",
	"created",
	"updated",
	"isOrigin",
	"mayInviteSelf",
	"mayInviteOthers",
	"hideAttendees",
)


class CalendarExchange(Document):
	@property
	def max_import(self) -> int:
		"""Returns the maximum number of events allowed for import."""

		return cint(get_config("exchange_max_import"))

	@property
	def max_export(self) -> int:
		"""Returns the maximum number of events allowed for export."""

		return cint(get_config("exchange_max_export"))

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
		if self.export_sort == "Start (DESC)":
			return [{"property": "start", "isAscending": False}]
		return [{"property": "start", "isAscending": True}]

	@property
	def import_metadata_dict(self) -> dict:
		"""Return the import metadata as a dictionary."""

		if self.operation != "Import" or not self.import_metadata:
			return {}

		return json.loads(self.import_metadata)

	@property
	def target_calendar_ids(self) -> dict[str, bool] | None:
		"""Returns the target calendar IDs for import, if specified."""

		return self.import_metadata_dict.get("calendarIds")

	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		if self.is_new():
			self.validate_account()

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

	def validate_account(self) -> None:
		"""Validate that the selected user can authenticate and has access to the account."""

		if not is_jmap_configured(self.user):
			frappe.throw(
				_("User {0} does not have JMAP settings configured.").format(frappe.bold(self.user)),
				frappe.PermissionError,
			)

		from mail.jmap import get_user_account_ids

		if self.account_id not in get_user_account_ids(self.user):
			frappe.throw(
				_("Account ID {0} is not accessible to user {1}.").format(
					frappe.bold(self.account_id), frappe.bold(self.user)
				),
				frappe.PermissionError,
			)

	def validate_import(self) -> None:
		"""Validate the import parameters."""

		if not self.import_format:
			frappe.throw(_("Import Format is required."))
		if not self.import_file:
			frappe.throw(_("Import File is required."))

		allowed_extensions = (".ics", ".zip", ".tgz", ".tar.gz")
		if not self.import_file.endswith(allowed_extensions):
			frappe.throw(
				_("Only {0} files are supported for import.").format(
					", ".join(f"<code>{ext}</code>" for ext in allowed_extensions)
				)
			)

		if self.import_metadata:
			try:
				self.import_metadata = json.dumps(json.loads(self.import_metadata), indent=4)
			except json.JSONDecodeError:
				frappe.throw(_("Metadata must be valid JSON."))

	def validate_export(self) -> None:
		"""Validate the export parameters."""

		if self.export_filter:
			try:
				self.export_filter = json.dumps(json.loads(self.export_filter), indent=4)
			except json.JSONDecodeError:
				frappe.throw(_("Export filter must be valid JSON."))

		if not self.export_archive_type:
			frappe.throw(_("Archive Type is required."))

		if not self.export_sort:
			self.export_sort = "Start (ASC)"

		if self.export_limit:
			export_limit = cint(self.export_limit)
			if export_limit <= 0:
				frappe.throw(_("Export Limit must be greater than zero."))
			if export_limit > self.max_export:
				frappe.throw(_("Export Limit cannot exceed {0}.").format(self.max_export))
			self.export_limit = export_limit
		else:
			self.export_limit = self.max_export

	def _get_logger(self) -> ExchangeLogger:
		"""Returns a structured event logger bound to this exchange's context."""

		return get_exchange_logger(
			{
				"req_id": random_string(10),
				"exchange": self.name,
				"kind": "calendar",
				"operation": self.operation,
				"user": self.user,
				"account_id": self.account_id,
			}
		)

	def process(self) -> None:
		"""Enqueue the import or export based on the operation type."""

		logger = self._get_logger()

		if self.operation == "Import":
			job_id = f"{self.name}:calendar:import"
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"_import",
				queue="long",
				timeout=cint(get_config("exchange_import_timeout")),
				job_id=job_id,
				deduplicate=True,
				enqueue_after_commit=True,
			)
			logger.debug("import-enqueued", job_id=job_id, format=self.import_format)
		elif self.operation == "Export":
			job_id = f"{self.name}:calendar:export"
			frappe.enqueue_doc(
				self.doctype,
				self.name,
				"_export",
				queue="long",
				timeout=cint(get_config("exchange_export_timeout")),
				job_id=job_id,
				deduplicate=True,
				enqueue_after_commit=True,
			)
			logger.debug("export-enqueued", job_id=job_id, format=self.export_format)

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retry the import or export."""

		frappe.only_for("System Manager")

		self._get_logger().info("retry-requested", status=self.status, retries=cint(self.retries))

		if self.docstatus != 1:
			frappe.throw(_("Only submitted calendar exchange can be retried."))
		elif self.status not in ["Queued", "In Progress", "Failed"]:
			frappe.throw(
				_("Only calendar exchange with status 'Queued', 'In Progress', or 'Failed' can be retried.")
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
		"""Imports the calendar events."""

		if self.operation != "Import":
			return

		logger = self._get_logger()
		logger.info("import-started", format=self.import_format, import_file=self.import_file)

		freeze_jmap_push_notifications(self.user)
		self._mark_started()
		self._log_output(_("Starting import from the uploaded {0} file.").format(self.import_format.upper()))

		import_file = os.path.join(get_bench_path(), f"sites/{frappe.local.site}{self.import_file}")
		base_dir = os.path.join(get_calendar_import_directory(), self.name)
		os.makedirs(base_dir, exist_ok=True)

		kwargs = {}
		try:
			if self.import_format == "ics" and self.import_file.endswith(".ics"):
				shutil.copy(import_file, os.path.join(base_dir, os.path.basename(import_file)))
			else:
				extract_compressed_file(import_file, base_dir)
			logger.debug("import-source-prepared", base_dir=base_dir)
			self._log_output(_("Prepared the source files for import."))

			service = get_calendar_event_service(self.user, self.account_id)

			if self.import_format == "ics":
				events = self._load_ics_events(service, base_dir, logger)
			else:
				events = self._load_jmap_events(base_dir)

			logger.info("import-events-loaded", events=len(events), max_import=self.max_import)
			self._log_output(_("Found {0} event(s) to import.").format(len(events)))

			if not events:
				frappe.throw(_("No calendar events found for import."))
			if len(events) > self.max_import:
				frappe.throw(_("Import limit exceeded."))

			created, skipped, failed = self._create_events(service, events, logger)

			logger.info("import-completed", created=created, skipped=skipped, failed=failed)
			self._log_output(
				_("Import completed. {0} created, {1} skipped (already present), {2} failed.").format(
					created, skipped, failed
				)
			)
			kwargs.update({"status": "Completed"})
		except Exception:
			logger.exception("import-failed")
			self._log_output(_("Import failed. See the error details below."))
			kwargs.update(
				{"status": "Failed", "output": f"{self.output}\n\n{frappe.get_traceback(with_context=False)}"}
			)
		finally:
			shutil.rmtree(base_dir, ignore_errors=True)
			unfreeze_jmap_push_notifications(self.user)

		self._mark_completed(**kwargs)
		self._notify_user(success=kwargs.get("status") == "Completed", action="Import")

	@reconnect_on_failure()
	def _export(self) -> None:
		"""Exports the calendar events."""

		if self.operation != "Export":
			return

		logger = self._get_logger()
		logger.info("export-started", format=self.export_format, archive_type=self.export_archive_type)

		self._mark_started()
		self._log_output(_("Starting export to {0} format.").format(self.export_format.upper()))
		out_dir = os.path.join(get_calendar_export_directory(), self.name)
		os.makedirs(out_dir, exist_ok=True)

		kwargs = {}
		try:
			service = get_calendar_event_service(self.user, self.account_id)

			limit = min(self.max_export, cint(self.export_limit or self.max_export))
			data = service.query(self.export_filter_dict, limit=limit, sort=self.export_sort_clause)
			ids = data.get("ids", [])
			total = data.get("total")
			logger.info("export-query-resolved", total=total, fetched=len(ids), max_export=self.max_export)
			self._log_output(
				_("Found {0} event(s) matching the filter; exporting up to {1}.").format(
					total if total is not None else len(ids), len(ids)
				)
			)

			if not ids:
				frappe.throw(_("No calendar events found for export."))

			events = service.get(ids)

			if self.deduplicate_export:
				fetched = len(events)
				unique: dict[str, dict] = {}
				for e in events:
					key = e.get("uid") or e.get("id")
					if key not in unique:
						unique[key] = e
				events = list(unique.values())
				logger.debug("export-deduplicated", fetched=fetched, unique=len(events))
				self._log_output(
					_("Removed {0} duplicate(s); {1} unique event(s) remain.").format(
						fetched - len(events), len(events)
					)
				)

			calendar_map = {c["id"]: c["name"] for c in service.calendars}
			CalendarExportWriter.write(self.export_format, events, out_dir, calendar_map)
			self._log_output(_("Wrote {0} event(s) to the export directory.").format(len(events)))

			self._log_output(
				_("Packaging exported events into a {0} archive.").format(self.export_archive_type)
			)
			self._attach_export(out_dir)

			logger.info("export-completed", events=len(events))
			self._log_output(_("Export completed successfully. {0} event(s) exported.").format(len(events)))
			kwargs.update({"status": "Completed"})
		except Exception:
			logger.exception("export-failed")
			self._log_output(_("Export failed. See the error details below."))
			kwargs.update(
				{"status": "Failed", "output": f"{self.output}\n\n{frappe.get_traceback(with_context=False)}"}
			)
		finally:
			shutil.rmtree(out_dir, ignore_errors=True)

		self._mark_completed(**kwargs)
		self._notify_user(success=kwargs.get("status") == "Completed", action="Export")

	def _load_ics_events(
		self, service: CalendarEventService, base_dir: str, logger: ExchangeLogger
	) -> list[dict]:
		"""Uploads every .ics file and parses it into JSCalendar events via the JMAP server."""

		ics_files = [
			os.path.join(root, f)
			for root, _dirs, files in os.walk(base_dir)
			for f in files
			if f.lower().endswith(".ics")
		]
		if not ics_files:
			frappe.throw(_("No .ics files found."))

		blob_to_file: dict[str, str] = {}
		for path in ics_files:
			with open(path, "rb") as f:
				data = f.read()
			blob_id = service.upload_blob(data, content_type="text/calendar; charset=utf-8").get("blobId")
			if blob_id:
				blob_to_file[blob_id] = path

		response = service.parse(list(blob_to_file.keys()))

		events: list[dict] = []
		for parsed in (response.get("parsed") or {}).values():
			for event in parsed or []:
				events.append(event)

		if not_parsable := response.get("notParsable"):
			logger.warning("import-ics-not-parsable", count=len(not_parsable))
			self._log_output(_("{0} file(s) could not be parsed and were skipped.").format(len(not_parsable)))

		return events

	def _load_jmap_events(self, base_dir: str) -> list[dict]:
		"""Loads JSCalendar events from the events.json file in the import directory."""

		path = os.path.join(base_dir, "events.json")
		if not os.path.exists(path):
			frappe.throw(_("events.json not found in the import directory."))

		with open(path) as f:
			events = json.load(f)

		if not isinstance(events, list):
			frappe.throw(_("events.json must contain a list of calendar events."))

		return events

	def _create_events(
		self, service: CalendarEventService, events: list[dict], logger: ExchangeLogger
	) -> tuple[int, int, int]:
		"""Creates the given JSCalendar events, skipping any whose UID already exists (idempotency).

		Returns a ``(created, skipped, failed)`` tuple. Failures within a batch are recorded and the
		remaining batches continue, so a few malformed events do not abort the whole import."""

		# Idempotency: skip events whose UID is already present in the account.
		uids = [e["uid"] for e in events if e.get("uid")]
		existing_uids: set[str] = set()
		if uids:
			if existing_ids := service.get_master_ids(uids):
				existing_uids = {e["uid"] for e in service.get(existing_ids) if e.get("uid")}

		default_calendar_id: str | None = None

		def resolve_calendar_ids(event: dict) -> dict:
			nonlocal default_calendar_id

			if self.target_calendar_ids:
				return self.target_calendar_ids
			if event.get("calendarIds"):
				return event["calendarIds"]
			if default_calendar_id is None:
				default_calendar_id = CalendarService(service.account_id, service.connection).get_default(
					raise_exception=True
				)
			return {default_calendar_id: True}

		pending: list[dict] = []
		skipped = 0
		for event in events:
			if event.get("uid") and event["uid"] in existing_uids:
				skipped += 1
				continue
			pending.append(event)

		created = 0
		failed = 0
		total = len(pending)
		for batch in create_batch(pending, service.max_objects_in_set):
			payload: dict[str, dict] = {}
			creation_to_uid: dict[str, str] = {}
			for event in batch:
				event = {k: v for k, v in event.items() if k not in SERVER_MANAGED_KEYS}
				event["@type"] = "Event"
				event["calendarIds"] = resolve_calendar_ids(event)

				creation_id = str(uuid7())
				payload[creation_id] = event
				creation_to_uid[creation_id] = event.get("uid", creation_id)

			response = service._create(payload, sendSchedulingMessages=False)
			method_responses = response.get("methodResponses") or []
			result = method_responses[0][1] if method_responses else {}

			batch_created = result.get("created") or {}
			batch_failed = result.get("notCreated") or {}
			created += len(batch_created)
			failed += len(batch_failed)

			for creation_id, error in batch_failed.items():
				logger.warning(
					"import-event-not-created",
					uid=creation_to_uid.get(creation_id),
					reason=str(error),
				)

			self._log_output(_("Imported {0} of {1} event(s).").format(created, total))

		return created, skipped, failed

	def _mark_started(self) -> None:
		"""Marks the calendar exchange as started and updates the started_at and started_after fields."""

		started_at = now()
		self._db_set(
			status="In Progress",
			started_at=started_at,
			started_after=time_diff_in_seconds(started_at, self.queued_at),
			output="",
		)

	def _mark_completed(self, **kwargs) -> None:
		"""Marks the calendar exchange as completed and updates the completed_at and duration fields."""

		kwargs["completed_at"] = now()
		kwargs["duration"] = time_diff_in_seconds(kwargs["completed_at"], self.started_at)

		if kwargs["status"] == "Failed":
			kwargs["retries"] = cint(self.retries) + 1

		self._db_set(**kwargs)

	def _attach_export(self, out_dir: str) -> None:
		"""Attaches the exported file to the calendar exchange."""

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
		"""Sends notification email to the owner of the calendar exchange."""

		if is_administrator(self.owner):
			return
		if not (email := get_user_email_address(self.owner)):
			return

		subject = _("Calendar Data {0} {1}").format(action, "Completed" if success else "Failed")
		frappe.publish_realtime(
			"calendar_exchange_completed",
			{"action": action, "success": success, "message": subject},
			user=self.user,
		)
		frappe.sendmail(
			recipients=email,
			subject=subject,
			template="generic",
			args={
				"title": subject,
				"description": _("View details for this exchange."),
				"button": _("View {0}").format(action),
				"link": get_url(f"/mail/calendar-exchanges/{self.name}"),
			},
			now=True,
		)

	def _log_output(self, message: str) -> None:
		"""Appends a timestamped, user-friendly line to the `output` field and persists it.

		These messages are surfaced in the UI so the user can follow the progress of the
		background import/export as it happens."""

		line = f"[{now()}] {message}"
		self.output = f"{self.output}\n{line}" if self.output else line
		self._db_set(output=self.output)

	def _db_set(self, **kwargs) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, notify=True, commit=True)


class CalendarExportWriter:
	@classmethod
	def write(
		cls,
		format: Literal["jmap", "ics"],
		events: list[dict],
		out_dir: str,
		calendar_map: dict[str, str],
	) -> None:
		"""Writes the exported events in the specified format."""

		writers = {
			"jmap": cls._jmap,
			"ics": cls._ics,
		}

		if format not in writers:
			frappe.throw(_("Unsupported export format: {0}").format(format))

		writers[format](events, out_dir, calendar_map)

	@staticmethod
	def _jmap(events: list[dict], out_dir: str, calendar_map: dict[str, str]) -> None:
		"""Writes the raw JSCalendar events and the calendar map (fully round-trippable)."""

		with open(os.path.join(out_dir, "events.json"), "w") as f:
			json.dump(events, f, indent=4)

		with open(os.path.join(out_dir, "calendars.json"), "w") as f:
			json.dump(calendar_map, f, indent=4)

	@staticmethod
	def _ics(events: list[dict], out_dir: str, calendar_map: dict[str, str]) -> None:
		"""Writes one VCALENDAR file per calendar, mirroring mbox's one-file-per-mailbox layout."""

		from icalendar import Calendar

		def safe_name(name: str) -> str:
			return (
				"".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in name).strip() or "calendar"
			)

		# Group events by the calendars they belong to (an event can live in several).
		by_calendar: dict[str, list[dict]] = {}
		for event in events:
			calendar_ids = list((event.get("calendarIds") or {}).keys()) or ["__default__"]
			for calendar_id in calendar_ids:
				by_calendar.setdefault(calendar_id, []).append(event)

		used_names: set[str] = set()
		for calendar_id, calendar_events in by_calendar.items():
			calendar_name = calendar_map.get(calendar_id, "Calendar")
			cal = Calendar()
			cal.add("prodid", "-//Frappe Mail//Calendar Exchange//EN")
			cal.add("version", "2.0")
			cal.add("method", "PUBLISH")

			for event in calendar_events:
				categories = [
					calendar_map[cid] for cid in (event.get("calendarIds") or {}) if cid in calendar_map
				]
				for component in _build_components(event, categories):
					cal.add_component(component)

			file_name = safe_name(calendar_name)
			candidate = file_name
			suffix = 1
			while candidate in used_names:
				suffix += 1
				candidate = f"{file_name}_{suffix}"
			used_names.add(candidate)

			with open(os.path.join(out_dir, f"{candidate}.ics"), "wb") as f:
				f.write(cal.to_ical())


def get_calendar_event_service(
	user: str,
	account_id: str,
	ignore_permissions: bool = False,
) -> CalendarEventService:
	"""Returns a CalendarEventService configured with the longer exchange timeouts."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, timeout=(60.0, 180.0))
	return CalendarEventService(account_id, connection)


def _parse_local_datetime(value: str | None, time_zone: str | None) -> datetime | None:
	"""Parses a JSCalendar LocalDateTime string into a (possibly timezone-aware) datetime."""

	if not value:
		return None

	dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
	if dt.tzinfo is None and time_zone:
		try:
			dt = dt.replace(tzinfo=ZoneInfo(time_zone))
		except Exception:
			pass

	return dt


def _parse_duration(value: str | None, start: datetime | None) -> timedelta | None:
	"""Parses an ISO 8601 duration string into a timedelta."""

	if not value:
		return None

	try:
		duration = isodate.parse_duration(value)
	except Exception:
		return None

	if isinstance(duration, timedelta):
		return duration

	# isodate.Duration (carries months/years): resolve against the start when available.
	try:
		return duration.totimedelta(start=start or datetime(2000, 1, 1))
	except Exception:
		return None


def _build_recurrence_rule(rule: dict) -> dict | None:
	"""Converts a JSCalendar RecurrenceRule object into an iCalendar RRULE value dict."""

	if not rule:
		return None

	recur: dict[str, list] = {}

	if frequency := rule.get("frequency"):
		recur["FREQ"] = [frequency.upper()]
	if (interval := rule.get("interval")) and cint(interval) > 1:
		recur["INTERVAL"] = [cint(interval)]
	if count := rule.get("count"):
		recur["COUNT"] = [cint(count)]
	if until := rule.get("until"):
		parsed = _parse_local_datetime(until, None)
		if parsed:
			recur["UNTIL"] = [parsed]
	if first_day := rule.get("firstDayOfWeek"):
		if mapped := WEEKDAY_MAP.get(first_day.lower()):
			recur["WKST"] = [mapped]

	if by_day := rule.get("byDay"):
		days = []
		for nday in by_day:
			day = WEEKDAY_MAP.get((nday.get("day") or "").lower())
			if not day:
				continue
			nth = nday.get("nthOfPeriod")
			days.append(f"{nth}{day}" if nth else day)
		if days:
			recur["BYDAY"] = days

	scalar_map = {
		"byMonthDay": "BYMONTHDAY",
		"byMonth": "BYMONTH",
		"byYearDay": "BYYEARDAY",
		"byWeekNo": "BYWEEKNO",
		"byHour": "BYHOUR",
		"byMinute": "BYMINUTE",
		"bySecond": "BYSECOND",
		"bySetPosition": "BYSETPOS",
	}
	for js_key, ical_key in scalar_map.items():
		if values := rule.get(js_key):
			recur[ical_key] = list(values)

	return recur or None


def _add_participants(component, participants: dict) -> None:
	"""Adds ATTENDEE properties to a VEVENT from a JSCalendar participants map."""

	from icalendar import vCalAddress

	for participant in (participants or {}).values():
		address = participant.get("calendarAddress") or (
			f"mailto:{participant['email']}" if participant.get("email") else None
		)
		if not address:
			continue

		attendee = vCalAddress(address)
		if name := participant.get("name"):
			attendee.params["CN"] = name

		roles = participant.get("roles") or {}
		role = next((PARTICIPANT_ROLE_MAP[r] for r in roles if r in PARTICIPANT_ROLE_MAP), None)
		if role:
			attendee.params["ROLE"] = role

		if kind := participant.get("kind"):
			if cutype := CUTYPE_MAP.get(kind.lower()):
				attendee.params["CUTYPE"] = cutype

		if partstat := participant.get("participationStatus"):
			if mapped := PARTSTAT_MAP.get(partstat.lower()):
				attendee.params["PARTSTAT"] = mapped

		attendee.params["RSVP"] = "TRUE" if participant.get("expectReply") else "FALSE"

		component.add("attendee", attendee, encode=0)


def _add_alarms(component, alerts: dict) -> None:
	"""Adds VALARM sub-components to a VEVENT from a JSCalendar alerts map."""

	from icalendar import Alarm

	for alert in (alerts or {}).values():
		action = (alert.get("action") or "display").upper()
		if action not in ("DISPLAY", "EMAIL", "AUDIO"):
			action = "DISPLAY"

		trigger = alert.get("trigger") or {}
		alarm = Alarm()
		alarm.add("action", action)

		trigger_type = trigger.get("@type")
		if trigger_type == "AbsoluteTrigger" and trigger.get("when"):
			when = _parse_local_datetime(trigger["when"], None)
			if when:
				alarm.add("trigger", when)
		else:
			offset = _parse_duration(trigger.get("offset", "-PT10M"), None)
			if offset is None:
				offset = timedelta(minutes=-10)
			related = (trigger.get("relativeTo") or "start").upper()
			alarm.add("trigger", offset, parameters={"RELATED": related})

		# DISPLAY/EMAIL alarms require a description per RFC 5545.
		alarm.add("description", component.get("summary") or "Reminder")
		if action == "EMAIL":
			alarm.add("summary", component.get("summary") or "Reminder")

		component.add_component(alarm)


def jscalendar_to_vevent(event: dict, categories: list[str] | None = None):
	"""Converts a single JSCalendar Event object into an iCalendar VEVENT component.

	Recurrence overrides are NOT applied here; :func:`_build_components` handles those by
	emitting the master event plus per-instance override components."""

	from icalendar import Event, vText

	component = Event()

	if uid := event.get("uid"):
		component.add("uid", uid)

	if title := event.get("title"):
		component.add("summary", title)
	if description := event.get("description"):
		component.add("description", description)

	time_zone = event.get("timeZone")
	start = _parse_local_datetime(event.get("start"), time_zone)
	if start:
		if event.get("showWithoutTime"):
			component.add("dtstart", start.date())
		else:
			component.add("dtstart", start)

	duration = _parse_duration(event.get("duration"), start)
	if duration is not None:
		if event.get("showWithoutTime"):
			# All-day events use a DATE-valued DTEND (exclusive) for broad client compatibility.
			if start:
				component.add("dtend", (start + (duration or timedelta(days=1))).date())
		else:
			component.add("duration", duration)

	if (status := event.get("status")) and status.lower() in STATUS_MAP:
		component.add("status", STATUS_MAP[status.lower()])
	if (privacy := event.get("privacy")) and privacy.lower() in PRIVACY_MAP:
		component.add("class", PRIVACY_MAP[privacy.lower()])
	if (free_busy := event.get("freeBusyStatus")) and free_busy.lower() in FREE_BUSY_MAP:
		component.add("transp", FREE_BUSY_MAP[free_busy.lower()])

	if organizer := event.get("organizerCalendarAddress"):
		component.add("organizer", vText(organizer))

	locations = [l.get("name") for l in (event.get("locations") or {}).values() if l.get("name")]
	if locations:
		component.add("location", "; ".join(locations))

	for link in (event.get("links") or {}).values():
		if href := link.get("href"):
			component.add("url", href)
			break

	if categories:
		component.add("categories", categories)

	recurrence_rule = event.get("recurrenceRule")
	if isinstance(recurrence_rule, list):
		recurrence_rule = recurrence_rule[0] if recurrence_rule else None
	if recur := _build_recurrence_rule(recurrence_rule):
		component.add("rrule", recur)

	created = _parse_local_datetime(event.get("created"), None)
	updated = _parse_local_datetime(event.get("updated"), None)
	if created:
		component.add("created", created)
	if updated:
		component.add("last-modified", updated)
	component.add("dtstamp", updated or created or datetime.now(UTC))

	if (sequence := event.get("sequence")) is not None:
		component.add("sequence", cint(sequence))

	_add_participants(component, event.get("participants"))
	_add_alarms(component, event.get("alerts"))

	return component


def _build_components(event: dict, categories: list[str] | None = None) -> list:
	"""Builds the VEVENT component(s) for an event: the master plus any recurrence overrides.

	Excluded instances become EXDATE entries on the master; modified instances become separate
	VEVENT components sharing the UID and carrying RECURRENCE-ID."""

	master = jscalendar_to_vevent(event, categories)
	components = [master]

	overrides = event.get("recurrenceOverrides") or {}
	time_zone = event.get("timeZone")
	excluded: list = []

	for recurrence_id, patch in overrides.items():
		instance_dt = _parse_local_datetime(recurrence_id, time_zone)
		if instance_dt is None:
			continue

		if patch.get("excluded"):
			excluded.append(instance_dt.date() if event.get("showWithoutTime") else instance_dt)
			continue

		# A modified instance: merge the master with the patch, drop the recurrence machinery,
		# and tag it with RECURRENCE-ID so clients reconcile it against the series.
		merged = {k: v for k, v in event.items() if k not in ("recurrenceRule", "recurrenceOverrides")}
		merged.update(patch)
		override = jscalendar_to_vevent(merged, categories)
		if event.get("showWithoutTime"):
			override.add("recurrence-id", instance_dt.date())
		else:
			override.add("recurrence-id", instance_dt)
		components.append(override)

	if excluded:
		master.add("exdate", excluded)

	return components


def get_permission_query_condition(user: str | None = None) -> str:
	user = user or frappe.session.user

	if is_system_manager(user) or is_mail_admin(user):
		return ""

	return f"(`tabCalendar Exchange`.user = '{user}')"


def has_permission(doc: Document, ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Calendar Exchange":
		return False

	user = user or frappe.session.user

	if is_system_manager(user) or is_mail_admin(user):
		return True

	return doc.user == user


def retry_stuck_calendar_exchanges() -> None:
	"""Called by the scheduler to retry stuck calendar exchanges."""

	CE = frappe.qb.DocType("Calendar Exchange")
	exchanges = (
		frappe.qb.from_(CE)
		.select(CE.name)
		.where(
			(CE.status.isin(["Queued", "In Progress"]))
			& (CE.queued_at <= get_datetime(add_to_date(now(), days=-1)))
		)
		.orderby(CE.queued_at, order=Order.asc)
	).run(pluck="name")

	for exchange in exchanges:
		frappe.get_doc("Calendar Exchange", exchange).retry()


def clean_calendar_import_export_directories() -> None:
	"""Called by the scheduler to clean up calendar import and export directories."""

	for base in (get_calendar_import_directory(), get_calendar_export_directory()):
		if not os.path.exists(base):
			continue

		for item in os.listdir(base):
			path = os.path.join(base, item)
			if os.path.isdir(path):
				if frappe.db.exists("Calendar Exchange", {"name": item, "status": "In Progress"}):
					continue
				shutil.rmtree(path, ignore_errors=True)
			else:
				os.remove(path)
