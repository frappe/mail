# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import Tuple
from frappe.query_builder import Order, Criterion
from mail.utils.cache import get_user_owned_domains
from frappe.query_builder.functions import Date, IfNull
from mail.utils.user import has_role, is_system_manager, get_user_mailboxes


def execute(filters=None) -> Tuple[list, list]:
	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data)

	return columns, data, None, None, summary


def get_data(filters=None) -> list:
	filters = filters or {}

	OM = frappe.qb.DocType("Outgoing Mail")
	MR = frappe.qb.DocType("Mail Recipient")

	query = (
		frappe.qb.from_(OM)
		.left_join(MR)
		.on(OM.name == MR.parent)
		.select(
			OM.name,
			OM.creation,
			MR.status,
			MR.retries,
			OM.message_size,
			OM.via_api,
			OM.is_newsletter,
			OM.submitted_after,
			OM.transferred_after,
			MR.action_after,
			OM.agent,
			OM.domain_name,
			OM.ip_address,
			OM.sender,
			MR.email.as_("recipient"),
			OM.message_id,
			OM.created_at,
			OM.submitted_at,
			OM.transfer_completed_at.as_("transferred_at"),
			MR.action_at,
		)
		.where((OM.docstatus == 1) & (IfNull(MR.status, "") != ""))
		.orderby(OM.creation, OM.created_at, order=Order.desc)
		.orderby(MR.idx, order=Order.asc)
	)

	if not filters.get("name") and not filters.get("message_id"):
		query = query.where(
			(Date(OM.created_at) >= Date(filters.get("from_date")))
			& (Date(OM.created_at) <= Date(filters.get("to_date")))
		)

	if not filters.get("include_newsletter"):
		query = query.where(OM.is_newsletter == 0)

	for field in [
		"name",
		"agent",
		"domain_name",
		"ip_address",
		"sender",
		"message_id",
	]:
		if filters.get(field):
			query = query.where(OM[field] == filters.get(field))

	for field in ["status", "email"]:
		if filters.get(field):
			query = query.where(MR[field] == filters.get(field))

	user = frappe.session.user
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

		query = query.where(Criterion.any(conditions))

	return query.run(as_dict=True)


def get_summary(data: list) -> list[dict]:
	status_count = {}
	total_message_size = 0
	total_transfer_delay = 0

	for row in data:
		status = row["status"]
		if status in ["Sent", "Deferred", "Bounced"]:
			status_count.setdefault(status, 0)
			status_count[status] += 1

		total_message_size += row["message_size"]
		total_transfer_delay += row["transferred_after"]

	return [
		{
			"value": status_count.get("Sent", 0),
			"indicator": "green",
			"label": "Total Sent",
			"datatype": "Int",
		},
		{
			"value": status_count.get("Deferred", 0),
			"indicator": "blue",
			"label": "Total Deferred",
			"datatype": "Int",
		},
		{
			"value": status_count.get("Bounced", 0),
			"indicator": "red",
			"label": "Total Bounced",
			"datatype": "Int",
		},
		{
			"value": total_message_size / len(data) if data else 0,
			"indicator": "blue",
			"label": "Average Message Size",
			"datatype": "Int",
		},
		{
			"value": total_transfer_delay / len(data) if data else 0,
			"indicator": "green",
			"label": "Average Transfer Delay",
			"datatype": "Int",
		},
	]


def get_columns() -> list:
	return [
		{
			"label": _("Name"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Outgoing Mail",
			"width": 100,
		},
		{
			"label": _("Creation"),
			"fieldname": "creation",
			"fieldtype": "Datetime",
			"width": 180,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Retries"),
			"fieldname": "retries",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Message Size"),
			"fieldname": "message_size",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("API"),
			"fieldname": "via_api",
			"fieldtype": "Check",
			"width": 60,
		},
		{
			"label": _("Newsletter"),
			"fieldname": "is_newsletter",
			"fieldtype": "Check",
			"width": 100,
		},
		{
			"label": _("Created After"),
			"fieldname": "submitted_after",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Transferred After"),
			"fieldname": "transferred_after",
			"fieldtype": "Int",
			"width": 140,
		},
		{
			"label": _("Action After"),
			"fieldname": "action_after",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Agent"),
			"fieldname": "agent",
			"fieldtype": "Link",
			"options": "Mail Agent",
			"width": 150,
		},
		{
			"label": _("Domain Name"),
			"fieldname": "domain_name",
			"fieldtype": "Link",
			"options": "Mail Domain",
			"width": 150,
		},
		{
			"label": _("IP Address"),
			"fieldname": "ip_address",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Sender"),
			"fieldname": "sender",
			"fieldtype": "Link",
			"options": "Mailbox",
			"width": 200,
		},
		{
			"label": _("Recipient"),
			"fieldname": "recipient",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Message ID"),
			"fieldname": "message_id",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Created At"),
			"fieldname": "created_at",
			"fieldtype": "Datetime",
			"width": 180,
		},
		{
			"label": _("Submitted At"),
			"fieldname": "submitted_at",
			"fieldtype": "Datetime",
			"width": 180,
		},
		{
			"label": _("Transferred At"),
			"fieldname": "transferred_at",
			"fieldtype": "Datetime",
			"width": 180,
		},
		{
			"label": _("Action At"),
			"fieldname": "action_at",
			"fieldtype": "Datetime",
			"width": 180,
		},
	]
