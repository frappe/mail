import frappe
from frappe import _
from frappe.utils import flt, cint
from frappe.model.document import Document
from mail.utils.cache import get_user_owned_domains
from mail.utils.user import has_role, is_system_manager


def validate_file(doc, method):
	"""Validates attachment attached to Outgoing Mail and Incoming Mail."""

	def _throw(msg, raise_exception=True, indicator="red", alert=True):
		frappe.msgprint(
			msg, raise_exception=raise_exception, indicator=indicator, alert=alert
		)

	if (
		doc.attached_to_doctype in ["Outgoing Mail", "Incoming Mail"] and doc.attached_to_name
	):
		docstatus = cint(
			frappe.db.get_value(doc.attached_to_doctype, doc.attached_to_name, "docstatus")
		)

		if method == "validate":
			if doc.is_new() and docstatus > 0:
				_throw(
					_("Cannot attach file to a submitted/cancelled {0} {1}.").format(
						doc.attached_to_doctype, frappe.bold(doc.attached_to_name)
					)
				)

			if doc.attached_to_doctype == "Outgoing Mail":
				file_size = flt(doc.file_size / 1024 / 1024, 3)
				max_attachment_size = frappe.db.get_single_value(
					"Mail Settings", "outgoing_max_attachment_size", cache=True
				)

				if file_size > max_attachment_size:
					_throw(
						_("Attachment size limit exceeded ({0} MB). Maximum {1} MB allowed.").format(
							frappe.bold(file_size), frappe.bold(max_attachment_size)
						)
					)

		elif method == "on_update":
			if docstatus > 0:
				_throw(
					_("Cannot update attachment as it is linked with {0} {1}.").format(
						doc.attached_to_doctype, frappe.bold(doc.attached_to_name)
					)
				)

		elif method == "on_trash":
			if docstatus > 0:
				_throw(
					_("Cannot delete attachment as it is linked with {0} {1}.").format(
						doc.attached_to_doctype, frappe.bold(doc.attached_to_name)
					)
				)


def user_has_permission(doc: Document, ptype: str, user: str) -> bool:
	if doc.doctype != "User":
		return False

	return (
		(user == doc.name)
		or is_system_manager(user)
		or (
			has_role(user, "Domain Owner")
			and (doc.email.split("@")[1] in get_user_owned_domains(user))
		)
	)


def get_user_permission_query_condition(user: str | None = None) -> str:
	conditions = []

	if not user:
		user = frappe.session.user

	if not is_system_manager(user):
		conditions.append(f"(`tabUser`.`name` = {frappe.db.escape(user)})")

		if has_role(user, "Domain Owner"):
			for domain in get_user_owned_domains(user):
				conditions.append(f"(`tabUser`.`email` LIKE '%@{domain}')")

	return " OR ".join(conditions)
