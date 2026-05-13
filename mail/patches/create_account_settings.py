import frappe

from mail.utils.user import get_user_personal_account


def execute() -> None:
	user_settings = frappe.get_all(
		"User Settings",
		{"username": ["!=", ""]},
		[
			"user",
			"email_previous_state",
			"email_current_state",
			"email_state_last_update",
			"last_active_sieve_script_id",
		],
	)

	for user_setting in user_settings:
		try:
			account = get_user_personal_account(user_setting.user, raise_exception=True)

			if frappe.db.exists("Account Settings", {"account": account}):
				continue

			account_settings = frappe.new_doc("Account Settings")
			account_settings.account = account
			account_settings.email_previous_state = user_setting.email_previous_state
			account_settings.email_current_state = user_setting.email_current_state
			account_settings.email_state_last_update = user_setting.email_state_last_update
			account_settings.last_active_sieve_script_id = user_setting.last_active_sieve_script_id
			account_settings.insert(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(
				message=f"Failed to create account settings for user {user_setting.user}: {e!s}",
				title="Failed to create Account Settings",
			)
