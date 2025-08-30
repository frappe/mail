# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def on_user_password_change(doc, method):
	"""Handle user password changes to update related mail account password."""

	# Check if password was actually changed
	if not doc.has_value_changed("password") and not doc.new_password:
		return

	# Find the related mail account for this user
	mail_account = frappe.db.get_value("Mail Account", {"user": doc.name}, "name")
	if not mail_account:
		return

	# Get the new password (either from password field or new_password field)
	new_password = doc.new_password or doc.get_password("password")
	if not new_password:
		return

	try:
		# Update the mail account password
		account_doc = frappe.get_doc("Mail Account", mail_account)
		account_doc.password = new_password
		account_doc.save(ignore_permissions=True)

		frappe.logger().info(f"Updated Mail Account password for user {doc.name}")

	except Exception as e:
		frappe.logger().error(f"Failed to update Mail Account password for user {doc.name}: {str(e)}")
