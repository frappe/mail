# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now, today
from frappe.utils.data import convert_utc_to_system_timezone, get_datetime

from mail.jmap import get_jmap_client
from mail.utils import convert_html_to_text
from mail.utils.dt import convert_to_utc
from mail.utils.validation import has_permission_for_user


class VacationResponse(Document):
	def db_insert(self, *args, **kwargs) -> None:
		raise NotImplementedError

	@frappe.whitelist()
	def load_from_db(self) -> "VacationResponse":
		self.user = self.get("user") or frappe.session.user

		if not self.user or self.user in ("Guest", "Administrator"):
			self.user = None
			frappe.msgprint(_("Please select a user to view vacation response details."), alert=True)
			return super(Document, self).__init__({"creation": today(), "modified": today()})

		vc = get_vacation_response(self.user)
		return super(Document, self).__init__(vc)

	def on_update(self) -> None:
		if not self.user or self.user in ("Guest", "Administrator"):
			return

		update_vacation_response(
			self.user,
			self.enabled,
			self.from_date,
			self.to_date,
			self.subject,
			self.text_body,
			self.html_body,
		)
		self.reload()

	def delete(self) -> None:
		raise NotImplementedError

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		pass

	@staticmethod
	def get_count(filters=None, **kwargs):
		pass

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}


@frappe.whitelist()
def get_vacation_response(user: str) -> dict:
	"""Returns the vacation response settings for the given user."""

	has_permission_for_user(user)

	client = get_jmap_client(user)
	vc = client.vacation_response_get()
	return format_vacation_response(user, vc)


@frappe.whitelist()
def update_vacation_response(
	user: str,
	enabled: bool | int,
	from_date: datetime | str | None = None,
	to_date: datetime | str | None = None,
	subject: str | None = None,
	text_body: str | None = None,
	html_body: str | None = None,
) -> None:
	"""Updates the vacation response settings for the given user."""

	has_permission_for_user(user)

	enabled = bool(enabled)
	from_date = convert_to_utc(from_date).isoformat() if from_date else None
	to_date = convert_to_utc(to_date).isoformat() if to_date else None

	if enabled and (from_date and to_date) and (from_date >= to_date):
		frappe.throw(_("To Date must be after From Date."))

	if not convert_html_to_text(html_body):
		html_body = None

	client = get_jmap_client(user)
	client.vacation_response_update(enabled, from_date, to_date, subject, text_body, html_body)


def format_vacation_response(user, vc: dict) -> dict:
	"""Formats the vacation response data."""

	from_date = vc.get("fromDate", None)
	local_from_date = convert_utc_to_system_timezone(get_datetime(from_date)) if from_date else None

	to_date = vc.get("toDate", None)
	local_to_date = convert_utc_to_system_timezone(get_datetime(to_date)) if to_date else None

	return {
		"user": user,
		"enabled": cint(vc.get("isEnabled")),
		"from_date": local_from_date,
		"to_date": local_to_date,
		"subject": vc.get("subject"),
		"text_body": vc.get("textBody"),
		"html_body": vc.get("htmlBody"),
		"creation": today(),
		"modified": today(),
	}


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Vacation Response":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
