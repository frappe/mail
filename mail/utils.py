import re
import frappe
import random
import socket
import ipaddress
import dns.resolver
from frappe import _
from mail.constants import NAMESERVERS


def get_dns_record(
	fqdn: str, type: str = "A", raise_exception: bool = False
) -> dns.resolver.Answer | None:
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


def is_valid_ip(ip: str, category: str = None) -> bool:
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
		"FM Server", filters={"enabled": 1, "outgoing": 1}, pluck="name"
	)

	if not servers:
		frappe.throw(_("No enabled outgoing server found."))

	return random.choice(servers)
