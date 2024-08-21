import re
import pytz
import frappe
import dns.resolver
from frappe import _
from typing import Callable
from datetime import datetime
from frappe.utils import get_system_timezone
from frappe.utils.caching import request_cache


def get_dns_record(
	fqdn: str, type: str = "A", raise_exception: bool = False
) -> dns.resolver.Answer | None:
	"""Returns DNS record for the given FQDN and type."""

	from mail.config.constants import NAMESERVERS

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


def get_host_by_ip(ip_address: str, raise_exception: bool = False) -> str | None:
	"""Returns host for the given IP address."""

	import socket

	err_msg = None

	try:
		return socket.gethostbyaddr(ip_address)[0]
	except Exception as e:
		err_msg = _(str(e))

	if raise_exception and err_msg:
		frappe.throw(err_msg)


def parsedate_to_datetime(
	date_header: str, to_timezone: str | None = None
) -> "datetime":
	"""Returns datetime object from parsed date header."""

	from email.utils import parsedate_to_datetime as parsedate

	dt = parsedate(date_header)
	if not dt:
		frappe.throw(_("Invalid date format: {0}").format(date_header))

	return dt.astimezone(pytz.timezone(to_timezone or get_system_timezone()))


def convert_to_utc(
	date_time: datetime | str, from_timezone: str | None = None
) -> "datetime":
	"""Converts the given datetime to UTC timezone."""

	from frappe.utils import get_datetime

	dt = get_datetime(date_time)
	if dt.tzinfo is None:
		tz = pytz.timezone(from_timezone or get_system_timezone())
		dt = tz.localize(dt)

	return dt.astimezone(pytz.utc)


@request_cache
def convert_html_to_text(html: str) -> str:
	"""Returns plain text from HTML content."""

	from bs4 import BeautifulSoup

	text = ""

	if html:
		soup = BeautifulSoup(html, "html.parser")
		text = soup.get_text()
		text = re.sub(r"\s+", " ", text).strip()

	return text


def get_in_reply_to(message_id: str) -> tuple[str, str] | tuple[None, None]:
	"""Returns mail type and name of the mail to which the given message is a reply to."""

	if message_id:
		for reply_to_mail_type in ["Outgoing Mail", "Incoming Mail"]:
			if reply_to_mail_name := frappe.db.get_value(
				reply_to_mail_type, {"message_id": message_id}, "name"
			):
				return reply_to_mail_type, reply_to_mail_name

	return None, None


def enqueue_job(method: str | Callable, **kwargs) -> None:
	"""Enqueues a background job."""

	from frappe.utils.background_jobs import get_jobs

	site = frappe.local.site
	jobs = get_jobs(site=site)
	if not jobs or method not in jobs[site]:
		frappe.enqueue(method, **kwargs)


def parse_iso_datetime(
	datetime_str: str, to_timezone: str | None = None, as_str: bool = True
) -> str | datetime:
	"""Converts ISO datetime string to datetime object in given timezone."""

	from frappe.utils import get_datetime_str

	if not to_timezone:
		to_timezone = get_system_timezone()

	dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00")).astimezone(
		pytz.timezone(to_timezone)
	)

	return get_datetime_str(dt) if as_str else dt
