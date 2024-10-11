import frappe
from frappe import _
from typing import Literal
from mail.mail.doctype.spam_check_log.spam_check_log import create_spam_check_log


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_spam_score(message: str) -> float:
	"""Returns the spam score of the message"""

	spam_log = create_spam_check_log(message)
	return spam_log.spam_score


@frappe.whitelist(methods=["POST"], allow_guest=True)
def is_spam(
	message: str, message_type: Literal["Inbound", "Outbound"] = "Outbound"
) -> bool:
	"""Returns True if the message is spam else False"""

	spam_log = create_spam_check_log(message)
	return spam_log.is_spam(message_type)
