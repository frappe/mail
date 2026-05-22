import csv
import io
import json
from typing import Literal

import frappe
from frappe import _
from frappe.query_builder.functions import Max
from frappe.utils import cint
from pypika import Case, Order

from mail.api.mail import get_avatar_url
from mail.stalwart import create_domain as create_stalwart_domain
from mail.stalwart import delete_domain as delete_stalwart_domain
from mail.stalwart import get_domains as get_stalwart_domains
from mail.utils import execute_with_logging, get_config
from mail.utils.dns import parse_dns_zone_file
from mail.utils.rate_limiter import dynamic_rate_limit
from mail.utils.user import is_mail_admin


def _get_stalwart_domain(domain_id: str) -> dict:
	"""Helper function to get a domain by ID from Stalwart, throwing a DoesNotExistError if not found."""

	domains = get_stalwart_domains()
	domain = next((d for d in domains if d["id"] == domain_id), None)

	if not domain:
		frappe.throw(_("Domain not found"), frappe.DoesNotExistError)

	return domain


@frappe.whitelist()
@dynamic_rate_limit()
def add_domain(name: str, description: str | None = None) -> str:
	"""Adds a new domain to Stalwart with the specified name and description, returning the new domain's ID."""

	for domain in get_stalwart_domains():
		if domain["name"].lower() == name.lower():
			frappe.throw(_("Domain {0} already exists.").format(name))

	domain_id = execute_with_logging(
		func=lambda: create_stalwart_domain(name, description),
		title=_("Failed to add domain {0}").format(name),
		user_message=_("An error occurred while adding the domain, check error logs for more details."),
		with_context=False,
	)
	return domain_id


@frappe.whitelist()
def get_domains(txt: str | None = None, is_enabled: bool | None = None) -> list[dict]:
	"""Returns the list of domains configured in Stalwart, with optional filtering by name/description and enabled status"""

	user = frappe.session.user
	if not is_mail_admin(user):
		frappe.throw(_("User {0} does not have Mail Admin role.").format(frappe.bold(user)))

	result = []
	for domain in get_stalwart_domains():
		if txt and (
			txt.lower() not in domain["name"].lower()
			and txt.lower() not in (domain.get("description") or "").lower()
		):
			continue

		if is_enabled is not None and domain["isEnabled"] != bool(is_enabled):
			continue

		result.append(
			{
				"id": domain["id"],
				"name": domain["name"],
				"description": domain.get("description", ""),
				"is_enabled": domain["isEnabled"],
				"created_at": domain["createdAt"],
			}
		)

	return result


@frappe.whitelist()
def get_domain(domain_id: str) -> dict:
	"""Returns the details of a domain, including its DNS records parsed from the zone file"""

	def infer_category(record: dict) -> str:
		"""Infers the category of the DNS record based on its type and name."""

		t = record["type"]
		name = record["name"]

		if t == "MX":
			return "Receiving"

		if t == "TXT":
			value = record["value"] or ""
			if name.startswith("_dmarc"):
				return "DMARC"
			if "spf1" in value:
				return "Sending"
			if "domainkey" in name:
				return "DKIM"
			if name.startswith("_smtp._tls"):
				return "TLS Reporting"
			return "TXT"

		if t == "CNAME":
			if "autoconfig" in name:
				return "Auto-config"
			if "autodiscover" in name:
				return "Auto-discover"
			return "Alias"

		if t == "SRV":
			if "_imap" in name or "_pop3" in name:
				return "Receiving"
			if "_submission" in name or "_submissions" in name:
				return "Sending"
			return "Server"

		return "Other"

	def is_mandatory(record: dict) -> bool:
		"""Define which DNS records are required."""

		category = record["category"]
		value = record["value"]

		if category == "Sending" and "spf1" in value:
			return True
		if category == "DMARC":
			return True
		if category == "DKIM":
			return True
		if record["type"] == "MX":
			return False

		return False

	domain = _get_stalwart_domain(domain_id)

	default_ttl = get_config("default_dns_ttl")
	dns_records = parse_dns_zone_file(domain["dnsZoneFile"])
	for record in dns_records:
		if not record["ttl"]:
			record["ttl"] = default_ttl
		record["category"] = infer_category(record)
		record["mandatory"] = is_mandatory(record)

	return {
		"id": domain["id"],
		"name": domain["name"],
		"description": domain.get("description", ""),
		"is_enabled": domain["isEnabled"],
		"created_at": domain["createdAt"],
		"dns_records": dns_records,
	}


@frappe.whitelist()
def delete_domain(domain_id: str) -> None:
	"""Deletes a domain identified by Stalwart domain ID."""

	user = frappe.session.user
	if not is_mail_admin(user):
		frappe.throw(_("User {0} does not have Mail Admin role.").format(frappe.bold(user)))

	execute_with_logging(
		func=lambda: delete_stalwart_domain(domain_id),
		title=_("Failed to delete domain with ID {0}").format(domain_id),
		user_message=_("An error occurred while deleting the domain, check error logs for more details."),
		with_context=False,
	)


@frappe.whitelist()
def get_enabled_domains() -> list[str]:
	"""Returns the list of enabled domains"""

	return list(set([d["name"] for d in get_stalwart_domains() if d["isEnabled"]]))


@frappe.whitelist()
def get_domain_dns_zone(domain_id: str) -> str:
	"""Returns the DNS zone file of the domain"""

	domain = _get_stalwart_domain(domain_id)
	return domain["dnsZoneFile"]


@frappe.whitelist()
def get_domain_dns_csv(domain_id: str) -> str:
	"""Returns the DNS records of the domain as a CSV string"""

	domain = _get_stalwart_domain(domain_id)
	dns_records = parse_dns_zone_file(domain["dnsZoneFile"])

	fieldnames = ["name", "ttl", "class", "type", "value"]

	output = io.StringIO()
	writer = csv.DictWriter(output, fieldnames=fieldnames)
	writer.writeheader()

	for record in dns_records:
		writer.writerow(record)

	return output.getvalue()


@frappe.whitelist()
def get_domain_dns_json(domain_id: str) -> str:
	"""Returns the DNS records of the domain as a JSON object"""

	domain = _get_stalwart_domain(domain_id)
	dns_records = parse_dns_zone_file(domain["dnsZoneFile"])
	return json.dumps(dns_records, indent=4)


@frappe.whitelist()
@dynamic_rate_limit()
def add_member(
	username: str,
	domain: str,
	is_admin: bool,
	send_invite: bool,
	backup_email: str,
	first_name: str | None = None,
	last_name: str | None = None,
	password: str | None = None,
	expires_at: str | None = None,
) -> None:
	"""Create a new Mail Account Request for adding a member"""

	account_request = frappe.new_doc("Mail Account Request")
	account_request.domain_name = domain
	account_request.account = f"{username}@{domain}"
	account_request.is_admin = cint(is_admin)
	account_request.invited_by = frappe.session.user
	account_request.backup_email = backup_email
	account_request.send_invite = cint(send_invite)
	account_request.expires_at = expires_at
	account_request.insert()

	if not send_invite:
		account_request.force_verify_and_create_account(first_name, last_name, password)


@frappe.whitelist()
def get_members(search: str | None = None, is_admin: bool | None = None) -> list:
	user = frappe.session.user

	if not is_mail_admin(user):
		frappe.throw(_("User {0} does not have Mail Admin role.").format(frappe.bold(user)))

	USER = frappe.qb.DocType("User")
	HAS_ROLE = frappe.qb.DocType("Has Role")
	USER_SETTINGS = frappe.qb.DocType("User Settings")

	admin_case = Case().when(HAS_ROLE.role == "Mail Admin", 1).else_(0)
	is_admin_expr = Max(admin_case)

	query = (
		frappe.qb.from_(USER)
		.left_join(HAS_ROLE)
		.on(USER.name == HAS_ROLE.parent)
		.left_join(USER_SETTINGS)
		.on(USER.name == USER_SETTINGS.user)
		.select(
			USER.name,
			USER.full_name,
			USER.user_image,
			USER.last_active,
			is_admin_expr.as_("is_admin"),
		)
		.where((USER.enabled == 1) & (USER_SETTINGS.username.isnotnull()))
		.groupby(USER.name)
	)

	if search:
		query = query.where(USER.name.like(f"%{search}%") | USER.full_name.like(f"%{search}%"))

	if is_admin is not None:
		query = query.having(is_admin_expr == (1 if is_admin else 0))

	users = (
		query.orderby(is_admin_expr, order=Order.desc).orderby(USER.name, order=Order.asc).run(as_dict=True)
	)

	for user in users:
		if not user.get("user_image"):
			user["user_image"] = get_avatar_url(user["name"])

		user["is_admin"] = bool(user.get("is_admin"))

	return users


@frappe.whitelist()
def get_account_requests(
	search: str | None = None, status: Literal["All", "Pending", "Accepted", "Expired"] = "All"
) -> list[dict]:
	"""Returns the list of account invites"""

	ACC_REQ = frappe.qb.DocType("Mail Account Request")
	query = (
		frappe.qb.from_(ACC_REQ)
		.select(
			ACC_REQ.name,
			ACC_REQ.account,
			ACC_REQ.is_admin,
			ACC_REQ.backup_email,
			ACC_REQ.invited_by,
			ACC_REQ.is_verified,
		)
		.orderby(ACC_REQ.creation, order=Order.desc)
	)

	if search:
		query = query.where(ACC_REQ.account.like(f"%{search}%"))

	if status == "Pending":
		query = query.where((ACC_REQ.is_verified == 0) & (ACC_REQ.expires_at > frappe.utils.now()))
	elif status == "Accepted":
		query = query.where(ACC_REQ.is_verified == 1)
	elif status == "Expired":
		query = query.where((ACC_REQ.is_verified == 0) & (ACC_REQ.expires_at <= frappe.utils.now()))

	invites = query.run(as_dict=True)

	return invites


@frappe.whitelist()
def delete_account_requests(names: list) -> None:
	"""Delete Mail Account Requests"""

	for d in names:
		frappe.delete_doc("Mail Account Request", d)
