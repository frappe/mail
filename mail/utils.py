import re
import frappe
import dns.resolver
from frappe import _
from frappe.frappeclient import FrappeClient
from typing import Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
	from datetime import datetime
	from email.message import Message


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


def get_random_outgoing_agent() -> str:
	"""Returns a random enabled outgoing mail agent."""

	import random

	agents = frappe.db.get_all(
		"Mail Agent", filters={"enabled": 1, "outgoing": 1}, pluck="name"
	)

	if not agents:
		frappe.throw(_("No enabled outgoing agent found."))

	return random.choice(agents)


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


def get_parsed_message(message: str) -> "Message":
	"""Returns parsed email message object from string."""

	from email import message_from_string

	return message_from_string(message)


def is_system_manager(user: str) -> bool:
	"""Returns True if the user is Administrator or System Manager else False."""

	return user == "Administrator" or has_role(user, "System Manager")


def get_postmaster() -> str:
	"""Returns the Postmaster from Mail Settings."""

	return (
		frappe.db.get_single_value("Mail Settings", "postmaster", cache=True)
		or "Administrator"
	)


def is_postmaster(user: str) -> bool:
	"""Returns True if the user is Postmaster else False."""

	return user == get_postmaster()


def get_user_mailboxes(user: str) -> list:
	"""Returns the list of mailboxes associated with the user."""

	return frappe.db.get_all("Mailbox", filters={"user": user}, pluck="name")


def is_mailbox_owner(mailbox: str, user: str) -> bool:
	"""Returns True if the mailbox is associated with the user else False."""

	return frappe.db.get_value("Mailbox", mailbox, "user") == user


def get_user_domains(user: str) -> list:
	"""Returns the list of domains associated with the user's mailboxes."""

	return list(
		set(frappe.db.get_all("Mailbox", filters={"user": user}, pluck="domain_name"))
	)


def get_user_owned_domains(user: str) -> list:
	"""Returns the list of domains owned by the user."""

	return frappe.db.get_all(
		"Mail Domain", filters={"domain_owner": user}, pluck="domain_name"
	)


def has_role(user: str, roles: str | list) -> bool:
	"""Returns True if the user has any of the given roles else False."""

	if isinstance(roles, str):
		roles = [roles]

	user_roles = frappe.get_roles(user)
	for role in roles:
		if role in user_roles:
			return True

	return False


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_outgoing_mails(
	doctype: Optional[str] = None,
	txt: Optional[str] = None,
	searchfield: Optional[str] = None,
	start: Optional[int] = 0,
	page_len: Optional[int] = 20,
	filters: Optional[dict] = None,
) -> list:
	"""Returns Outgoing Mails on which the user has select permission."""

	from frappe.query_builder import Order, Criterion

	user = frappe.session.user

	OM = frappe.qb.DocType("Outgoing Mail")
	query = (
		frappe.qb.from_(OM)
		.select(OM.name)
		.where((OM.docstatus == 1) & (OM[searchfield].like(f"%{txt}%")))
		.orderby(OM.creation, OM.created_at, order=Order.desc)
		.offset(start)
		.limit(page_len)
	)

	if not is_system_manager(user):
		conditions = []
		domains = get_user_owned_domains(user)
		mailboxes = get_user_mailboxes(user)

		if has_role(user, "Domain Owner") and domains:
			conditions.append(OM.domain_name.isin(domains))

		if has_role(user, "Mailbox User") and mailboxes:
			conditions.append(OM.sender.isin(mailboxes))

		if not conditions:
			return []

		query = query.where((Criterion.any(conditions)))

	return query.run(as_dict=False)


def get_agent_client(agent: str) -> FrappeClient:
	"""Returns FrappeClient object for the given agent."""

	if hasattr(frappe.local, "agent_clients"):
		if client := frappe.local.agent_clients.get(agent):
			return client
	else:
		frappe.local.agent_clients = {}

	agent = frappe.get_cached_doc("Mail Agent", agent)
	url = f"{agent.protocol}://{agent.host or agent.agent}"
	api_key = agent.agent_api_key
	api_secret = agent.get_password("agent_api_secret")

	frappe.local.agent_clients[agent.agent] = FrappeClient(
		url, api_key=api_key, api_secret=api_secret
	)

	return get_agent_client(agent.agent)


def validate_mail_folder(
	folder: str, validate_for: Literal["inbound", "outbound"]
) -> None:
	"""Validates if the folder is an inbound or outbound folder."""

	if not frappe.get_cached_value("Mail Folder", folder, validate_for):
		folder_name = frappe.get_cached_value("Mail Folder", folder, "folder_name")
		frappe.throw(
			_("Folder {0} is not an {1} folder.").format(frappe.bold(folder_name), validate_for)
		)
