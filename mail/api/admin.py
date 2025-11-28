from typing import TYPE_CHECKING, Literal

import frappe
from frappe import _
from frappe.query_builder import Case, Order
from frappe.utils import cint

from mail.utils.rate_limiter import dynamic_rate_limit
from mail.utils.user import is_tenant_admin

if TYPE_CHECKING:
	from mail.client.doctype.mail_domain_request.mail_domain_request import MailDomainRequest


@frappe.whitelist()
def create_tenant(tenant_name: str) -> None:
	"""Create a new Mail Tenant"""

	tenant = frappe.new_doc("Mail Tenant")
	tenant.tenant_name = tenant_name
	tenant.user = frappe.session.user
	tenant.insert(ignore_permissions=True)


@frappe.whitelist()
def get_domain_request(domain_name: str, mail_tenant: str) -> "MailDomainRequest":
	"""Fetches Mail Domain Request for a given domain name if it exists, and creates a new one if not"""

	if frappe.db.exists("Mail Domain", domain_name):
		frappe.throw(_("Domain {0} has already been registered.").format(frappe.bold(domain_name)))

	if name := frappe.db.exists("Mail Domain Request", {"domain_name": domain_name, "tenant": mail_tenant}):
		return frappe.get_doc("Mail Domain Request", name)

	domain_request = frappe.new_doc("Mail Domain Request")
	domain_request.domain_name = domain_name
	domain_request.tenant = mail_tenant
	domain_request.user = frappe.session.user
	domain_request.insert()

	return domain_request


@frappe.whitelist()
@dynamic_rate_limit()
def verify_dns_record(domain_request: str) -> bool:
	"""Verify the domain request key"""

	doc = frappe.get_doc("Mail Domain Request", domain_request)
	return doc.verify_and_create_domain(save=True)


@frappe.whitelist()
def get_tenant_members(tenant: str, search: str, role: str) -> list:
	"""Returns list of members for the given tenant"""

	user = frappe.session.user
	if not is_tenant_admin(tenant, user):
		frappe.throw(_("User {0} is not a Mail Admin of Tenant {1}.").format(user, tenant))

	MTM = frappe.qb.DocType("Mail Tenant Member")
	User = frappe.qb.DocType("User")
	owner = frappe.db.get_value("Mail Tenant", tenant, "user")
	sort_order = (
		Case()
		.when(MTM.user == owner, 0)  # Owner First
		.when(MTM.is_admin == 1, 1)  # Admins Second
		.else_(2)  # Members Last
	)

	query = (
		frappe.qb.from_(MTM)
		.left_join(User)
		.on(MTM.user == User.name)
		.select(
			User.name,
			User.full_name,
			User.user_image,
			MTM.is_admin,
			sort_order,
		)
		.where((MTM.tenant == tenant) & (User.name.like(f"%{search}%") | User.full_name.like(f"%{search}%")))
	)

	if role:
		is_admin = 1 if role == "Mail Admin" else 0
		query = query.where(MTM.is_admin == is_admin)

	return (query.orderby(sort_order, order=Order.asc).orderby(MTM.name, order=Order.asc)).run(as_dict=True)


@frappe.whitelist()
@dynamic_rate_limit()
def add_member(
	tenant: str,
	username: str,
	domain: str,
	role: Literal["Mail User", "Mail Admin"],
	send_invite: bool,
	email: str,
	expires_at: str | None = None,
	first_name: str | None = None,
	last_name: str | None = None,
	password: str | None = None,
) -> None:
	"""Create a new Mail Account Request for adding a member"""

	account_request = frappe.new_doc("Mail Account Request")
	account_request.is_invite = 1
	account_request.tenant = tenant
	account_request.domain_name = domain
	account_request.account = f"{username}@{domain}"
	account_request.is_admin = cint(role == "Mail Admin")
	account_request.invited_by = frappe.session.user
	account_request.email = email
	account_request.send_invite = cint(send_invite)
	account_request.expires_at = expires_at
	account_request.insert()

	if not send_invite:
		account_request.force_verify_and_create_account(first_name, last_name, password)


@frappe.whitelist()
def delete_aliases(names: list) -> None:
	"""Delete Mail Aliases"""

	for d in names:
		frappe.delete_doc("Mail Alias", d)


@frappe.whitelist()
def delete_mailing_lists(names: list) -> None:
	"""Delete Mailing Lists"""

	for d in names:
		doc = frappe.get_doc("Mailing List", d)
		doc.enabled = 0
		frappe.db.delete("Mailing List Member", {"mailing_list": d})
		doc.delete()


@frappe.whitelist()
def add_list_members(list: str, type: Literal["Mail Account", "Mail Group"], members: list) -> None:
	"""Adds members to a Mailing List"""

	for d in members:
		MGM = frappe.new_doc("Mailing List Member")
		MGM.mailing_list = list
		MGM.member_type = type
		MGM.member_name = d
		MGM.insert()


@frappe.whitelist()
def delete_list_members(names: list, is_external: bool) -> None:
	"""Delete Mailing List Members"""

	doctype = "Mailing List External Member" if is_external else "Mailing List Member"
	frappe.db.delete(doctype, {"name": ["in", names]})


@frappe.whitelist()
def delete_account_requests(names: list) -> None:
	"""Delete Mail Account Requests"""

	for d in names:
		frappe.delete_doc("Mail Account Request", d)
