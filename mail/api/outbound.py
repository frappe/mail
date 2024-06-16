import json
import frappe
from typing import Any
from frappe.utils import cint
from email.utils import parseaddr
from mail.mail.doctype.outgoing_mail.outgoing_mail import create_outgoing_mail


@frappe.whitelist(methods=["POST"])
def send() -> str:
	"""Send Mail."""

	data = get_decoded_data()
	validate_mail(data)
	mail = get_mail_dict(data)
	doc = create_outgoing_mail(**mail)

	return doc.name


@frappe.whitelist(methods=["POST"])
def send_batch() -> list[str]:
	"""Send Mails in Batch."""

	data = get_decoded_data()
	validate_batch(data)

	doc_list = []
	for mail in data:
		mail = get_mail_dict(mail, send_in_batch=1)
		doc = create_outgoing_mail(**mail)
		doc_list.append(doc.name)

	return doc_list


@frappe.whitelist(methods=["POST"])
def send_raw() -> str:
	"""Send Raw Mail."""

	data = get_decoded_data()
	validate_raw(data)
	mail = get_mail_dict(data)
	doc = create_outgoing_mail(**mail)

	return doc.name


def get_decoded_data() -> Any:
	"""Returns the decoded data from the request."""

	return json.loads(frappe.request.data.decode())


def validate_mail(data: Any) -> None:
	"""Validates the mail data."""

	if not data or not isinstance(data, dict):
		raise frappe.ValidationError("Invalid Data")

	mandatory_fields = ["from", "to", "subject"]
	validate_mandatory_fields(data, mandatory_fields)


def validate_batch(data: Any) -> None:
	"""Validates the batch data."""

	if not data or not isinstance(data, list):
		raise frappe.ValidationError("Invalid Data")

	if len(data) > 100:
		raise frappe.ValidationError("Batch size cannot exceed 100.")

	for mail in data:
		validate_mail(mail)


def validate_raw(data: Any) -> None:
	"""Validates the raw data."""

	if not data or not isinstance(data, dict):
		raise frappe.ValidationError("Invalid Data")

	mandatory_fields = ["from", "to", "raw_message"]
	validate_mandatory_fields(data, mandatory_fields)


def validate_mandatory_fields(data: dict, fields: list[str]) -> None:
	"""Validates the mandatory fields in the data."""

	for field in fields:
		if not data.get(field):
			raise frappe.ValidationError(f"{field} is mandatory.")


def get_mail_dict(data: dict, send_in_batch: int = 0) -> dict:
	"""Returns the mail dict."""

	mail = {
		# Mandatory Fields
		"sender": parseaddr(data["from"])[1],
		"to": data["to"],
		# Optional Fields
		"cc": data.get("cc"),
		"bcc": data.get("bcc"),
		"raw_message": data.get("raw_message"),
		# Flags
		"via_api": 1,
		"send_in_batch": send_in_batch,
	}

	if not mail["raw_message"]:
		mail.update(
			{
				# Mandatory Fields
				"subject": data["subject"],
				# Optional Fields
				"raw_html": data.get("html"),
				"track": cint(data.get("track")),
				"reply_to": data.get("reply_to"),
				"custom_headers": data.get("headers"),
				"attachments": data.get("attachments"),
			}
		)

	return mail
