import re
import frappe
from frappe import _
from typing import Literal, Optional


def is_valid_host(host: str) -> bool:
	"""Returns True if the host is a valid hostname else False."""

	return bool(re.compile(r"^[a-zA-Z0-9_]+$").match(host))


def is_valid_ip(ip: str, category: Optional[str] = None) -> bool:
	"""Returns True if the IP is valid else False."""

	import ipaddress

	try:
		ip_obj = ipaddress.ip_address(ip)

		if category:
			if category == "private":
				return ip_obj.is_private
			elif category == "public":
				return not ip_obj.is_private

		return True
	except ValueError:
		return False


def is_port_open(fqdn: str, port: int) -> bool:
	"""Returns True if the port is open else False."""

	import socket

	try:
		with socket.create_connection((fqdn, port), timeout=10):
			return True
	except (socket.timeout, socket.error):
		return False


def is_valid_email_for_domain(
	email: str, domain_name: str, raise_exception: bool = False
) -> bool:
	"""Returns True if the email domain matches with the given domain else False."""

	email_domain = email.split("@")[1]

	if not email_domain == domain_name:
		if raise_exception:
			frappe.throw(
				_("Email domain {0} does not match with domain {1}.").format(
					frappe.bold(email_domain), frappe.bold(domain_name)
				)
			)

		return False
	return True


def validate_active_domain(domain_name: str) -> None:
	"""Validates if the domain is enabled and verified."""

	if frappe.session.user == "Administrator" or frappe.flags.ingore_domain_validation:
		return

	enabled, verified = frappe.get_cached_value(
		"Mail Domain", domain_name, ["enabled", "verified"]
	)

	if not enabled:
		frappe.throw(_("Domain {0} is disabled.").format(frappe.bold(domain_name)))
	if not verified:
		frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(domain_name)))


def validate_mailbox_for_outgoing(mailbox: str) -> None:
	"""Validates if the mailbox is enabled and allowed for outgoing mail."""

	enabled, status, outgoing = frappe.get_cached_value(
		"Mailbox", mailbox, ["enabled", "status", "outgoing"]
	)

	if not enabled:
		frappe.throw(_("Mailbox {0} is disabled.").format(frappe.bold(mailbox)))
	elif status != "Active":
		frappe.throw(_("Mailbox {0} is not active.").format(frappe.bold(mailbox)))
	elif not outgoing:
		frappe.throw(
			_("Mailbox {0} is not allowed for Outgoing Mail.").format(frappe.bold(mailbox))
		)


def validate_mailbox_for_incoming(mailbox: str) -> None:
	"""Validates if the mailbox is enabled and allowed for incoming mail."""

	enabled, status, incoming = frappe.get_cached_value(
		"Mailbox", mailbox, ["enabled", "status", "incoming"]
	)

	if not enabled:
		frappe.throw(_("Mailbox {0} is disabled.").format(frappe.bold(mailbox)))
	elif status != "Active":
		frappe.throw(_("Mailbox {0} is not active.").format(frappe.bold(mailbox)))
	elif not incoming:
		frappe.throw(
			_("Mailbox {0} is not allowed for Incoming Mail.").format(frappe.bold(mailbox))
		)
