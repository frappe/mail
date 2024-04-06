import re
import pytz
import frappe
import random
import socket
import ipaddress
import dns.resolver
from frappe import _
from typing import Optional
from bs4 import BeautifulSoup
from datetime import datetime
from mail.constants import NAMESERVERS
from frappe.utils import get_system_timezone


def get_dns_record(
	fqdn: str, type: str = "A", raise_exception: bool = False
) -> Optional[dns.resolver.Answer]:
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
		err_msg = _(e)

	if raise_exception and err_msg:
		frappe.throw(err_msg)


def is_valid_host(host: str) -> bool:
	return bool(re.compile(r"^[a-zA-Z0-9_]+$").match(host))


def is_valid_ip(ip: str, category: Optional[str] = None) -> bool:
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
	try:
		with socket.create_connection((fqdn, port), timeout=1):
			return True
	except (socket.timeout, socket.error):
		return False


def get_outgoing_server() -> str:
	servers = frappe.db.get_all(
		"Mail Server", filters={"enabled": 1, "outgoing": 1}, pluck="name"
	)

	if not servers:
		frappe.throw(_("No enabled outgoing server found."))

	return random.choice(servers)


def parsedate_to_datetime(
	date_header: str, to_timezone: Optional[str] = None
) -> datetime:
	date_header = re.sub(r"\s+\([A-Z]+\)", "", date_header)
	dt = datetime.strptime(date_header, "%a, %d %b %Y %H:%M:%S %z")

	if not to_timezone:
		to_timezone = get_system_timezone()

	return dt.astimezone(pytz.timezone(to_timezone))


def convert_html_to_text(self, html: str) -> str:
	text = ""

	if html:
		soup = BeautifulSoup(html, "html.parser")
		text = soup.get_text()
		text = re.sub(r"\s+", " ", text).strip()

	return text


def is_valid_email_for_domain(
	email: str, domain_name: str, raise_exception: bool = False
) -> bool:
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
	enabled, status, mailbox_type = frappe.db.get_value(
		"Mailbox", mailbox, ["enabled", "status", "mailbox_type"]
	)

	if not enabled:
		frappe.throw(_("Mailbox {0} is disabled.").format(frappe.bold(mailbox)))
	elif status != "Active":
		frappe.throw(_("Mailbox {0} is not active.").format(frappe.bold(mailbox)))
	elif mailbox_type not in ["Outgoing", "Incoming and Outgoing"]:
		frappe.throw(
			_("Mailbox {0} is not allowed for Outgoing Mail.").format(frappe.bold(mailbox))
		)


def validate_mailbox_for_incoming(mailbox: str) -> None:
	enabled, status, mailbox_type = frappe.db.get_value(
		"Mailbox", mailbox, ["enabled", "status", "mailbox_type"]
	)

	if not enabled:
		frappe.throw(_("Mailbox {0} is disabled.").format(frappe.bold(mailbox)))
	elif status != "Active":
		frappe.throw(_("Mailbox {0} is not active.").format(frappe.bold(mailbox)))
	elif mailbox_type not in ["Incoming", "Incoming and Outgoing"]:
		frappe.throw(
			_("Mailbox {0} is not allowed for Incoming Mail.").format(frappe.bold(mailbox))
		)
