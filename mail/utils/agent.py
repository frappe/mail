import frappe
from frappe import _
from mail.mail.doctype.mail_agent.rabbitmq import RabbitMQ


def get_random_outgoing_agent() -> str:
	"""Returns a random enabled outgoing mail agent."""

	from random import choice

	agents = frappe.cache.get_value("outgoing_mail_agents")

	if not agents:
		MA = frappe.qb.DocType("Mail Agent")
		agents = (
			frappe.qb.from_(MA).select(MA.name).where((MA.enabled == 1) & (MA.outgoing == 1))
		).run(pluck="name")

		if agents:
			frappe.cache.set_value("outgoing_mail_agents", agents)
		else:
			frappe.throw(_("No enabled outgoing agent found."))

	return choice(agents)


def get_agent_rabbitmq_connection(agent: str) -> "RabbitMQ":
	"""Returns `RabbitMQ` object for the given agent."""

	agent = frappe.get_cached_doc("Mail Agent", agent)

	host = agent.rmq_host
	port = agent.rmq_port
	username = agent.rmq_username
	password = agent.get_password("rmq_password") if agent.rmq_password else None

	return RabbitMQ(host=host, port=port, username=username, password=password)
