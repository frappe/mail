import frappe


def after_install() -> None:
	create_mail_agent_job_types()


def after_migrate() -> None:
	create_mail_agent_job_types()


def create_mail_agent_job_types() -> None:
	"""Creates default Mail Agent Job Types."""

	agent_job_types = [
		{
			"enabled": 1,
			"job_name": "Transfer Mail",
			"request_path": "mail_agent.api.outgoing.send",
			"request_method": "POST",
			"queue": "short",
			"execute_on_start": "mail.mail.doctype.outgoing_mail.outgoing_mail.update_outgoing_mails_status",
			"execute_on_end": "mail.mail.doctype.outgoing_mail.outgoing_mail.update_outgoing_mails_status",
		},
		{
			"enabled": 1,
			"job_name": "Transfer Mails",
			"request_path": "mail_agent.api.outgoing.send",
			"request_method": "POST",
			"queue": "long",
			"execute_on_start": "mail.mail.doctype.outgoing_mail.outgoing_mail.update_outgoing_mails_status",
			"execute_on_end": "mail.mail.doctype.outgoing_mail.outgoing_mail.update_outgoing_mails_status",
		},
		{
			"enabled": 1,
			"job_name": "Sync Outgoing Mails Status",
			"request_path": "mail_agent.api.outgoing.sync_status",
			"request_method": "POST",
			"execute_on_end": "mail.mail.doctype.outgoing_mail.outgoing_mail.update_outgoing_mails_delivery_status",
		},
		{
			"enabled": 1,
			"job_name": "Sync Mail Domains",
			"request_path": "mail_agent.api.domain.sync",
			"request_method": "POST",
		},
		{
			"enabled": 1,
			"job_name": "Sync Mailboxes",
			"request_path": "mail_agent.api.mailbox.sync",
			"request_method": "POST",
		},
		{
			"enabled": 1,
			"job_name": "Sync Mail Aliases",
			"request_path": "mail_agent.api.alias.sync",
			"request_method": "POST",
		},
		{
			"enabled": 1,
			"job_name": "Sync Incoming Mails",
			"request_path": "mail_agent.api.incoming.sync",
			"request_method": "POST",
			"execute_on_end": "mail.mail.doctype.incoming_mail.incoming_mail.insert_incoming_mails",
		},
	]

	for agent_job_type in agent_job_types:
		if not frappe.db.exists("Mail Agent Job Type", agent_job_type["job_name"]):
			doc = frappe.new_doc("Mail Agent Job Type")
			doc.update(agent_job_type)
			doc.insert(ignore_permissions=True)
