# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import re
import frappe
import subprocess
from frappe import _
from typing import Literal
from email import message_from_string
from mail.utils import get_host_by_ip
from frappe.query_builder import Interval
from frappe.model.document import Document
from email.mime.multipart import MIMEMultipart
from frappe.query_builder.functions import Now


class SpamCheckLog(Document):
	@staticmethod
	def clear_old_logs(days=14):
		log = frappe.qb.DocType("Spam Check Log")
		frappe.db.delete(log, filters=(log.creation < (Now() - Interval(days=days))))

	def validate(self) -> None:
		if self.is_new():
			self.set_source_ip_address()
			self.set_source_host()
			self.scan_message()

	def set_source_ip_address(self) -> None:
		"""Sets the source IP address"""

		self.source_ip_address = frappe.local.request_ip

	def set_source_host(self) -> None:
		"""Sets the source host"""

		self.source_host = get_host_by_ip(self.source_ip_address)

	def scan_message(self) -> None:
		"""Scans the message for spam"""

		mail_settings = frappe.get_cached_doc("Mail Settings")

		if not mail_settings.enable_spam_detection:
			frappe.throw(_("Spam Detection is disabled"))

		scanned_message = None
		spamd_host = mail_settings.spamd_host
		spamd_port = mail_settings.spamd_port
		scanning_mode = mail_settings.scanning_mode
		hybrid_scanning_threshold = mail_settings.hybrid_scanning_threshold

		if scanning_mode == "Hybrid Approach":
			message_without_attachments = get_message_without_attachments(self.message)
			initial_result = scan_message(spamd_host, spamd_port, message_without_attachments)
			initial_spam_score = extract_spam_score(initial_result)

			if initial_spam_score < hybrid_scanning_threshold:
				scanned_message = initial_result

		elif scanning_mode == "Exclude Attachments":
			self.message = get_message_without_attachments(self.message)

		scanned_message = scanned_message or scan_message(
			spamd_host, spamd_port, self.message
		)
		self.spam_headers = "\n".join(
			f"{k}: {v}" for k, v in extract_spam_headers(scanned_message).items()
		)
		self.scanning_mode = scanning_mode
		self.hybrid_scanning_threshold = hybrid_scanning_threshold
		self.spam_score = extract_spam_score(scanned_message)

	def is_spam(self, message_type: Literal["Inbound", "Outbound"] = "Outbound") -> bool:
		"""Returns True if the message is spam else False"""

		max_spam_score_field = (
			"max_spam_score_for_outbound"
			if message_type == "Outbound"
			else "max_spam_score_for_inbound"
		)
		max_spam_score = frappe.db.get_single_value(
			"Mail Settings", max_spam_score_field, cache=True
		)

		return self.spam_score > max_spam_score


def create_spam_check_log(message: str) -> SpamCheckLog:
	"""Creates a Spam Check Log document"""

	doc = frappe.new_doc("Spam Check Log")
	doc.message = message
	doc.insert(ignore_permissions=True)

	return doc


def get_message_without_attachments(message: str) -> str:
	"""Returns the message without attachments"""

	parsed_message = message_from_string(message)
	message_without_attachments = MIMEMultipart()

	for header, value in parsed_message.items():
		message_without_attachments[header] = value

	for part in parsed_message.walk():
		if part.get_content_maintype() == "multipart":
			continue
		if part.get("Content-Disposition") is None:
			message_without_attachments.attach(part)

	return message_without_attachments.as_string()


def scan_message(host: str, port: int, message: str) -> str:
	"""Scans the message for spam"""

	process = subprocess.Popen(
		["spamc", "-d", host, "-p", str(port)],
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
	)
	stdout, stderr = process.communicate(input=message.encode("utf-8"))

	if stderr:
		frappe.log_error(title=_("Spam Detection Error"), message=stderr.decode())

	return stdout.decode()


def extract_spam_score(scanned_message: str) -> float:
	"""Extracts the spam score from the scanned message"""

	if match := re.search(r"X-Spam-Status:.*score=([\d\.]+)", scanned_message):
		return float(match.group(1))

	frappe.throw(_("Spam score not found in output."))


def extract_spam_headers(scanned_message: str) -> dict:
	"""Extracts the spam headers from the scanned message"""

	parsed_message = message_from_string(scanned_message)
	spam_headers = {
		key: value for key, value in parsed_message.items() if key.startswith("X-Spam-")
	}

	return spam_headers
