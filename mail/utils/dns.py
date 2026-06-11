import re
import socket

import dns.resolver
import frappe
from frappe import _


def get_dns_record(fqdn: str, type: str = "A", raise_exception: bool = False) -> dns.resolver.Answer | None:
	"""Returns DNS record for the given FQDN and type."""

	err_msg = None

	try:
		resolver = dns.resolver.Resolver(configure=False)
		resolver.nameservers = [
			"1.1.1.1",
			"8.8.4.4",
			"8.8.8.8",
			"9.9.9.9",
		]

		r = resolver.resolve(fqdn, type)
		return r
	except dns.resolver.NXDOMAIN:
		err_msg = _("{0} does not exist.").format(frappe.bold(fqdn))
	except dns.resolver.NoAnswer:
		err_msg = _("No answer for {0}.").format(frappe.bold(fqdn))
	except dns.exception.DNSException as e:
		err_msg = _(str(e))

	if raise_exception and err_msg:
		frappe.throw(err_msg)


def get_host_by_ip(ip_address: str, raise_exception: bool = False) -> str | None:
	"""Returns host for the given IP address."""

	err_msg = None

	try:
		return socket.gethostbyaddr(ip_address)[0]
	except Exception as e:
		err_msg = _(str(e))

	if raise_exception and err_msg:
		frappe.throw(err_msg)


def verify_dns_record(fqdn: str, type: str, expected_value: str, debug: bool = False) -> bool:
	"""Verifies the DNS Record."""

	if result := get_dns_record(fqdn, type):
		for data in result:
			if data:
				if type == "MX":
					data = data.exchange
				data = data.to_text().replace('"', "")
				if type == "TXT" and "._domainkey." in fqdn:
					data = data.replace(" ", "")
					expected_value = expected_value.replace(" ", "")
				if data == expected_value:
					return True
			if debug:
				frappe.msgprint(f"Expected: {expected_value} Got: {data}")
	return False


def parse_dns_zone_file(zone_file: str) -> list[dict]:
	"""Parses a DNS zone file content and returns a list of DNS records with their components."""

	# ------------------------------------------------------------
	# Step 1: Merge multiline DNS records
	# ------------------------------------------------------------
	merged_records = []
	buffer = []
	inside_multiline = False

	for line in zone_file.splitlines():
		line = line.strip()

		if not line:
			continue

		if "(" in line:
			inside_multiline = True

		buffer.append(line)

		if inside_multiline:
			if ")" in line:
				merged_records.append(" ".join(buffer))
				buffer = []
				inside_multiline = False
		else:
			merged_records.append(line)
			buffer = []

	# Safety: flush remaining buffer
	if buffer:
		merged_records.append(" ".join(buffer))

	# ------------------------------------------------------------
	# Step 2: Parse records
	# ------------------------------------------------------------
	dns_records = []

	for record in merged_records:
		# Remove multiline parentheses
		record = record.replace("(", "").replace(")", "").strip()

		# Normalize multiple spaces
		record = re.sub(r"\s+", " ", record)

		parts = record.split()

		# Minimum valid structure:
		# name IN TYPE value
		if len(parts) < 4:
			continue

		name = parts[0]

		# Handle optional TTL
		#
		# Formats:
		# example.com. 3600 IN TXT "value"
		# example.com. IN TXT "value"
		#
		if re.fullmatch(r"\d+", parts[1]):
			ttl = parts[1]
			record_class = parts[2]
			record_type = parts[3]
			value = " ".join(parts[4:])
		else:
			ttl = None
			record_class = parts[1]
			record_type = parts[2]
			value = " ".join(parts[3:])

		# Merge adjacent quoted TXT chunks:
		# "abc" "def" -> "abcdef"
		if record_type == "TXT":
			quoted_parts = re.findall(r'"([^"]*)"', value)

			if quoted_parts:
				value = "".join(quoted_parts)

		dns_records.append(
			{
				"name": name,
				"ttl": ttl,
				"class": record_class,
				"type": record_type,
				"value": value,
			}
		)

	return dns_records
