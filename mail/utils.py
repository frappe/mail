import frappe
import socket
import ipaddress
from frappe import _
import dns.resolver


class Utils:
	@staticmethod
	def get_dns_record(
		fqdn: str, type: str = "A", raise_exception: bool = False
	) -> dns.resolver.Answer | None:
		err_msg = None

		try:
			resolver = dns.resolver.Resolver(configure=False)
			resolver.nameservers = frappe.db.get_single_value(
				"FM Settings", "dns_nameservers"
			).split()

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
	def is_valid_domain(domain: str, raise_exception: bool = False) -> bool:
		return bool(Utils.get_dns_record(domain, "SOA", raise_exception=raise_exception))

	@staticmethod
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

	@staticmethod
	def is_port_open(fqdn: str, port: int) -> bool:
		try:
			with socket.create_connection((fqdn, port), timeout=1):
				return True
		except (socket.timeout, socket.error):
			return False
