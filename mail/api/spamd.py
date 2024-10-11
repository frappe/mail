import re
import frappe
import subprocess
from frappe import _
from typing import Literal
from email import message_from_string
from email.mime.multipart import MIMEMultipart


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_spam_score(message: str) -> float:
	return get_spam_score_for_email(message)


@frappe.whitelist(methods=["POST"], allow_guest=True)
def is_spam(
	message: str, email_type: Literal["Inbound", "Outbound"] = "Outbound"
) -> bool:
	spam_score = get_spam_score_for_email(message)
	max_spam_score_field = (
		"max_spam_score_for_outbound"
		if email_type == "Outbound"
		else "max_spam_score_for_inbound"
	)
	max_spam_score = frappe.db.get_single_value(
		"Mail Settings", max_spam_score_field, cache=True
	)

	return spam_score > max_spam_score


def get_spam_score_for_email(message: str) -> float:
	if result := scan_email_for_spam(message):
		return extract_spam_score(result)

	return 0.0


def extract_spam_score(message: str) -> float:
	if match := re.search(r"X-Spam-Status:.*score=([\d\.]+)", message):
		return float(match.group(1))

	return 0.0


def get_spam_headers(message: str) -> dict:
	if result := scan_email_for_spam(message):
		parsed_message = message_from_string(result)
		return {
			key: value for key, value in parsed_message.items() if key.startswith("X-Spam-")
		}

	return {}


def scan_email_for_spam(message: str) -> str:
	mail_settings = frappe.get_cached_doc("Mail Settings")

	if not mail_settings.enable_spam_detection:
		frappe.throw(_("Spam Detection is disabled"))

	spamd_host = mail_settings.spamd_host
	spamd_port = mail_settings.spamd_port
	scanning_mode = mail_settings.scanning_mode

	if scanning_mode == "Exclude Attachments":
		message = remove_attachments_from_email(message)
		return scan_with_spamassassin(spamd_host, spamd_port, message)
	elif scanning_mode == "Include Attachments":
		return scan_with_spamassassin(spamd_host, spamd_port, message)
	elif scanning_mode == "Hybrid Approach":
		email_without_attachments = remove_attachments_from_email(message)
		initial_result = scan_with_spamassassin(
			spamd_host, spamd_port, email_without_attachments
		)
		spam_score = extract_spam_score(initial_result)

		if spam_score < mail_settings.hybrid_scanning_threshold:
			return initial_result
		else:
			return scan_with_spamassassin(spamd_host, spamd_port, message)
	else:
		frappe.throw(_("Spam Detection Error - Invalid Scanning Mode"))


def remove_attachments_from_email(message: str) -> str:
	parsed_message = message_from_string(message)
	email_without_attachments = MIMEMultipart()

	for header, value in parsed_message.items():
		email_without_attachments[header] = value

	for part in parsed_message.walk():
		if part.get_content_maintype() == "multipart":
			continue
		if part.get("Content-Disposition") is None:
			email_without_attachments.attach(part)

	return email_without_attachments.as_string()


def scan_with_spamassassin(host: str, port: int, message: str) -> str:
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
