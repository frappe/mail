import frappe


def execute():
	frappe.db.set_single_value("Mail Settings", "default_ttl", "3600")
