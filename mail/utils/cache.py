import frappe
from frappe import _


def get_root_domain_name() -> str | None:
	"""Returns the root domain name."""

	def generator() -> str | None:
		return frappe.db.get_single_value("Mail Settings", "root_domain_name")

	return frappe.cache.hget("mail-settings", "root_domain_name", generator)


def get_signup_domains() -> list:
	"""Returns the signup domains."""

	def generator() -> list:
		mail_settings = frappe.get_doc("Mail Settings")
		principals = [d.principal for d in mail_settings.signup_domains]
		return frappe.db.get_all("Principal Settings", {"name": ["in", principals]}, pluck="principal_name")

	return frappe.cache.hget("mail-settings", "signup_domains", generator)


def get_account_emails(user: str) -> list:
	"""Returns the list of emails associated with the user."""

	def generator() -> list:
		from mail.jmap import get_identities

		return [i["email"] for i in get_identities(user)]

	return frappe.cache.hget(f"user|{user}", "emails", generator)


def get_rate_limits(method_path: str) -> list:
	"""Returns the rate limits for the method path."""

	def generator() -> list:
		RATE_LIMIT = frappe.qb.DocType("Rate Limit")
		rate_limits = (
			frappe.qb.from_(RATE_LIMIT)
			.select(
				RATE_LIMIT.ignore_in_developer_mode,
				RATE_LIMIT.key_.as_("key"),
				RATE_LIMIT.limit,
				RATE_LIMIT.seconds,
				RATE_LIMIT.methods,
				RATE_LIMIT.ip_based,
				RATE_LIMIT.allowed_ips,
				RATE_LIMIT.blocked_ips,
			)
			.where((RATE_LIMIT.enabled == 1) & (RATE_LIMIT.method_path == method_path))
		).run(as_dict=True)

		if not rate_limits:
			return []

		for rl in rate_limits:
			rl["ignore_in_developer_mode"] = bool(rl["ignore_in_developer_mode"])
			rl["methods"] = rl["methods"].split("\n")
			rl["ip_based"] = bool(rl["ip_based"])

			if len(rl["methods"]) == 1 and rl["methods"][0] == "ALL":
				rl["methods"] = "ALL"

			rl["allowed_ips"] = rl["allowed_ips"].split("\n") if rl["allowed_ips"] else []
			rl["blocked_ips"] = rl["blocked_ips"].split("\n") if rl["blocked_ips"] else []

		return rate_limits

	return frappe.cache.hget("rate_limits", method_path, generator)
