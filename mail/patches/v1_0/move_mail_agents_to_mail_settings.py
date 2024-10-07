import frappe


def execute():
	if not frappe.db.exists("Mail Agent"):
		return

	mail_settings = frappe.get_doc("Mail Settings")

	if mail_agent_groups := frappe.db.get_all(
		"Mail Agent Group", filters={"enabled": 1}, fields=["host", "priority"]
	):
		for group in mail_agent_groups:
			mail_settings.append(
				"mail_agents", {"type": "Inbound", "host": group.host, "priority": group.priority}
			)

	if mail_agents := frappe.db.get_all(
		"Mail Agent", filters={"enabled": 1, "outgoing": 1}, fields=["agent"]
	):
		for agent in mail_agents:
			mail_settings.append("mail_agents", {"type": "Outbound", "host": agent.agent})

	mail_settings.ignore_mandatory = True
	mail_settings.ignore_permissions = True
	mail_settings.save()
