import frappe
from mail.utils.cache import get_user_owned_domains
from mail.utils.user import has_role, is_system_manager, get_user_mailboxes


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_outgoing_mails(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
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
