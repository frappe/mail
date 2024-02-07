import frappe


def after_install() -> None:
	create_agent_job_types()


def after_migrate() -> None:
	create_agent_job_types()


def create_agent_job_types() -> None:
	agent_job_types = [
		{
			"enabled": 1,
			"job_name": "Send Mail",
			"request_path": "sendmail",
			"request_method": "POST",
			"execute_on_end": "mail.mail.doctype.fm_outgoing_email.fm_outgoing_email.update_delivery_status",
		},
	]

	for agent_job_type in agent_job_types:
		if not frappe.db.exists("FM Agent Job Type", agent_job_type["job_name"]):
			doc = frappe.new_doc("FM Agent Job Type")
			doc.update(agent_job_type)
			doc.insert(ignore_permissions=True)
