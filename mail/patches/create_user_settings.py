import frappe


def execute() -> None:
	users = frappe.db.get_all("User", {"jmap_username": ["!=", ""]}, pluck="name")

	for user in users:
		if frappe.db.exists("User Settings", {"user": user}):
			continue

		user_doc = frappe.get_doc("User", user)

		user_settings = frappe.new_doc("User Settings")
		user_settings.user = user
		# JMAP Credentials
		user_settings.server_url = user_doc.jmap_server_url
		user_settings.username = user_doc.jmap_username
		user_settings.app_password = user_doc.get_password("jmap_app_password")
		# JMAP State
		user_settings.email_previous_state = user_doc.jmap_email_previous_state
		user_settings.email_current_state = user_doc.jmap_email_current_state
		user_settings.email_state_last_update = user_doc.jmap_email_state_last_update
		# JMAP Settings
		user_settings.default_outgoing_email = user_doc.jmap_default_outgoing_email
		user_settings.destroy_email_after_submit = user_doc.jmap_destroy_email_after_submit
		user_settings.destroy_newsletter_after_submit = user_doc.jmap_destroy_newsletter_after_submit
		# Recovery
		user_settings.backup_email = user_doc.backup_email

		user_settings.insert(ignore_permissions=True)
