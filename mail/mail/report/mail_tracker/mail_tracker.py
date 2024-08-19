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


def get_data(filters=None) -> list:
	filters = filters or {}

	OM = frappe.qb.DocType("Outgoing Mail")
	query = (
		frappe.qb.from_(OM)
		.select(
			OM.name,
			OM.creation,
			OM.status,
			OM.open_count,
			OM.agent,
			OM.domain_name,
			OM.sender,
			OM.message_id,
			OM.tracking_id,
			OM.created_at,
			OM.first_opened_at,
			OM.last_opened_at,
			OM.last_opened_from_ip,
		)
		.where((OM.track == 1) & (OM.docstatus == 1))
		.orderby(OM.creation, OM.created_at, order=Order.desc)
	)

	if (
		not filters.get("name")
		and not filters.get("message_id")
		and not filters.get("tracking_id")
	):
		query = query.where(
			(Date(OM.created_at) >= Date(filters.get("from_date")))
			& (Date(OM.created_at) <= Date(filters.get("to_date")))
		)

	for field in [
		"name",
		"status",
		"agent",
		"domain_name",
		"sender",
		"message_id",
		"tracking_id",
	]:
		if filters.get(field):
			query = query.where(OM[field] == filters.get(field))

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
			"label": _("Open Count"),
			"fieldname": "open_count",
			"fieldtype": "Int",
			"width": 130,
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
			"label": _("Sender"),
			"fieldname": "sender",
			"fieldtype": "Link",
			"options": "Mailbox",
			"width": 200,
		},
		{
			"label": _("Message ID"),
			"fieldname": "message_id",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Tracking ID"),
			"fieldname": "tracking_id",
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
			"label": _("First Opened At"),
			"fieldname": "first_opened_at",
			"fieldtype": "Datetime",
			"width": 180,
		},
		{
			"label": _("Last Opened At"),
			"fieldname": "last_opened_at",
			"fieldtype": "Datetime",
			"width": 180,
		},
		{
			"label": _("Last Opened From IP"),
			"fieldname": "last_opened_from_ip",
			"fieldtype": "Data",
			"width": 120,
		},
	]
