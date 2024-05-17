import re
import pytz
import frappe
import random
import socket
import ipaddress
import dns.resolver
from frappe import _
from bs4 import BeautifulSoup
from datetime import datetime
from email import message_from_string
from typing import Optional, TYPE_CHECKING
from frappe.utils import get_system_timezone
from mail.config.constants import NAMESERVERS

if TYPE_CHECKING:
	from email.message import Message


def get_dns_record(
	fqdn: str, type: str = "A", raise_exception: bool = False
) -> Optional[dns.resolver.Answer]:
	"""Returns DNS record for the given FQDN and type."""

	err_msg = None

	try:
		resolver = dns.resolver.Resolver(configure=False)
		resolver.nameservers = NAMESERVERS

		return resolver.resolve(fqdn, type)
	except dns.resolver.NXDOMAIN:
		err_msg = _("{0} does not exist.".format(frappe.bold(fqdn)))
	except dns.resolver.NoAnswer:
		err_msg = _("No answer for {0}.".format(frappe.bold(fqdn)))
	except dns.exception.DNSException as e:
		err_msg = _(str(e))

	if raise_exception and err_msg:
		frappe.throw(err_msg)


def is_valid_host(host: str) -> bool:
	"""Returns True if the host is a valid hostname else False."""

	return bool(re.compile(r"^[a-zA-Z0-9_]+$").match(host))


def is_valid_ip(ip: str, category: Optional[str] = None) -> bool:
	"""Returns True if the IP is valid else False."""

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

	try:
		with socket.create_connection((fqdn, port), timeout=10):
			return True
	except (socket.timeout, socket.error):
		return False


def get_random_outgoing_agent() -> str:
	"""Returns a random enabled outgoing mail agent."""

	agents = frappe.db.get_all(
		"Mail Agent", filters={"enabled": 1, "outgoing": 1}, pluck="name"
	)

	if not agents:
		frappe.throw(_("No enabled outgoing agent found."))

	return random.choice(agents)


def parsedate_to_datetime(
	date_header: str, to_timezone: Optional[str] = None
) -> datetime:
	"""Returns datetime object from parsed date header."""

	date_header = re.sub(r"\s+\([A-Z]+\)", "", date_header)
	dt = datetime.strptime(date_header, "%a, %d %b %Y %H:%M:%S %z")

	return dt.astimezone(pytz.timezone(to_timezone or get_system_timezone()))


def convert_html_to_text(self, html: str) -> str:
	"""Returns plain text from HTML content."""

	text = ""

	if html:
		soup = BeautifulSoup(html, "html.parser")
		text = soup.get_text()
		text = re.sub(r"\s+", " ", text).strip()

	return text


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

	enabled, verified = frappe.db.get_value(
		"Mail Domain", domain_name, ["enabled", "verified"]
	)

	if not enabled:
		frappe.throw(_("Domain {0} is disabled.").format(frappe.bold(domain_name)))
	if not verified:
		frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(domain_name)))


def validate_mailbox_for_outgoing(mailbox: str) -> None:
	"""Validates if the mailbox is enabled and allowed for outgoing mail."""

	enabled, status, outgoing = frappe.db.get_value(
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

	enabled, status, incoming = frappe.db.get_value(
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


def get_parsed_message(original_message: str) -> "Message":
	"""Returns parsed email message object from string."""

	return message_from_string(original_message)


def is_system_manager(user: str) -> bool:
	"""Returns True if the user is Administrator or System Manager else False."""

	return user == "Administrator" or "System User" in frappe.get_roles(user)
