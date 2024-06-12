import frappe
from frappe import _
from frappe.frappeclient import FrappeClient


def get_random_outgoing_agent() -> str:
	"""Returns a random enabled outgoing mail agent."""

	import random

	agents = frappe.db.get_all(
		"Mail Agent", filters={"enabled": 1, "outgoing": 1}, pluck="name"
	)

	if not agents:
		frappe.throw(_("No enabled outgoing agent found."))

	return random.choice(agents)


def get_agent_client(agent: str) -> FrappeClient:
	"""Returns FrappeClient object for the given agent."""

	if hasattr(frappe.local, "agent_clients"):
		if client := frappe.local.agent_clients.get(agent):
			return client
	else:
		frappe.local.agent_clients = {}

	agent = frappe.get_cached_doc("Mail Agent", agent)
	url = f"{agent.protocol}://{agent.host or agent.agent}"
	api_key = agent.agent_api_key
	api_secret = agent.get_password("agent_api_secret")

	client = FrappeClient(url, api_key=api_key, api_secret=api_secret)
	frappe.local.agent_clients[agent.agent] = client

	return client
