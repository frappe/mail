import frappe


def after_install() -> None:
	create_daemon_user()
	create_agent_job_types()


def after_migrate() -> None:
	create_daemon_user()
	create_agent_job_types()


def create_daemon_user() -> None:
	if not frappe.db.exists("User", "daemon@frappemail.com"):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "daemon@frappemail.com",
				"first_name": "Daemon",
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		)
		user.add_roles("System Manager")
		user.save(ignore_permissions=True)


def create_agent_job_types() -> None:
	agent_job_types = [
		{
			"enabled": 1,
			"job_name": "Send Mail",
			"request_path": "mail_agent.api.sendmail",
			"request_method": "POST",
			"execute_on_end": "mail.mail.doctype.outgoing_mail.outgoing_mail.update_delivery_status",
		},
	]

	for agent_job_type in agent_job_types:
		if not frappe.db.exists("Mail Agent Job Type", agent_job_type["job_name"]):
			doc = frappe.new_doc("Mail Agent Job Type")
			doc.update(agent_job_type)
			doc.insert(ignore_permissions=True)
