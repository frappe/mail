import frappe
from frappe import _
from mail.rabbitmq import RabbitMQ


def get_random_outgoing_mail_agent() -> str:
	"""Returns a random enabled outgoing mail agent."""

	from random import choice
	from mail.utils.cache import get_outgoing_mail_agents

	outgoing_mail_agents = get_outgoing_mail_agents()

	if not get_outgoing_mail_agents:
		frappe.throw(_("No enabled outgoing agent found."))

	return choice(outgoing_mail_agents)


def get_agent_rabbitmq_connection(agent: str) -> "RabbitMQ":
	"""Returns `RabbitMQ` object for the given agent."""

	agent = frappe.get_cached_doc("Mail Agent", agent)

	host = agent.rmq_host
	port = agent.rmq_port
	username = agent.rmq_username
	password = agent.get_password("rmq_password") if agent.rmq_password else None

	return RabbitMQ(host=host, port=port, username=username, password=password)
