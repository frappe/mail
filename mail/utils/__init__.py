import re
import frappe
import dns.resolver
from frappe import _
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
	from datetime import datetime


def get_dns_record(
	fqdn: str, type: str = "A", raise_exception: bool = False
) -> Optional[dns.resolver.Answer]:
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


def parsedate_to_datetime(
	date_header: str, to_timezone: Optional[str] = None
) -> "datetime":
	"""Returns datetime object from parsed date header."""

	import pytz
	from datetime import datetime
	from frappe.utils import get_system_timezone

	date_header = re.sub(r"\s+\([A-Z]+\)", "", date_header)
	dt = datetime.strptime(date_header, "%a, %d %b %Y %H:%M:%S %z")

	return dt.astimezone(pytz.timezone(to_timezone or get_system_timezone()))


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
