import frappe
from mail.mail.doctype.ip_blacklist.ip_blacklist import get_blacklist_for_ip_address


@frappe.whitelist(methods=["GET"], allow_guest=True)
def get(ip_address: str) -> dict:
	"""Returns the blacklist for the given IP address."""

	return (
		get_blacklist_for_ip_address(ip_address, create_if_not_exists=True, commit=True) or {}
	)
