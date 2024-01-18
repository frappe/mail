import frappe
import dns.resolver
from frappe import _
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from mail.mail.doctype.fm_settings.fm_settings import FMSettings
	from mail.mail.doctype.fm_outgoing_server.fm_outgoing_server import FMOutgoingServer


class Utils:
	@staticmethod
	def get_dns_record(
		fqdn: str, type: str = "A", raise_exception: bool = False
	) -> dns.resolver.Answer | None:
		from mail.constants import NAMESERVERS

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

	@staticmethod
	def is_valid_host(host: str) -> bool:
		import re

		pattern = re.compile(r"^[a-zA-Z0-9_]+$")

		return bool(pattern.match(host))

	@staticmethod
	def is_valid_ip(ip: str, category: str = None) -> bool:
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

	@staticmethod
	def is_port_open(fqdn: str, port: int) -> bool:
		import socket

		try:
			with socket.create_connection((fqdn, port), timeout=1):
				return True
		except (socket.timeout, socket.error):
			return False

	@staticmethod
	def get_smtp_server(fm_settings: "FMSettings" = None) -> "FMOutgoingServer":
		import random

		if not fm_settings:
			fm_settings = frappe.get_cached_doc("FM Settings")

		return random.choice(fm_settings.outgoing_servers)
