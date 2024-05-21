# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import Tuple
from frappe.query_builder.functions import Date
from frappe.query_builder import Order, Criterion
from mail.utils import (
	has_role,
	is_system_manager,
	get_user_mailboxes,
	get_user_owned_domains,
)


def execute(filters=None) -> Tuple[list, list]:
	columns = get_columns()
	data = get_data(filters)

	return columns, data


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
			"label": _("Send in Batch"),
			"fieldname": "send_in_batch",
			"fieldtype": "Check",
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
			"label": _("From IP"),
			"fieldname": "from_ip",
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
			OM.send_in_batch,
			OM.transferred_after,
			MR.action_after,
			OM.agent,
			OM.domain_name,
			OM.from_ip,
			OM.sender,
			MR.recipient,
			OM.message_id,
			OM.created_at,
			OM.transferred_at,
			MR.action_at,
		)
		.where((OM.docstatus == 1))
		.orderby(OM.creation, OM.created_at, order=Order.desc)
		.orderby(MR.idx, order=Order.asc)
	)

	if not filters.get("name") and not filters.get("message_id"):
		query = query.where(
			(Date(OM.created_at) >= Date(filters.get("from_date")))
			& (Date(OM.created_at) <= Date(filters.get("to_date")))
		)

	for field in [
		"name",
		"agent",
		"domain_name",
		"from_ip",
		"sender",
		"message_id",
	]:
		if filters.get(field):
			query = query.where(OM[field] == filters.get(field))

	for field in ["status", "recipient"]:
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
