import frappe
from frappe import _

from mail.server.doctype.mail_principal_binding.mail_principal_binding import get_principal_tenant


def get_root_domain_name() -> str | None:
	"""Returns the root domain name."""

	def generator() -> str | None:
		return frappe.db.get_single_value("Mail Settings", "root_domain_name")

	return frappe.cache.hget("mail-settings", "root_domain_name", generator)


def get_personal_signup_domains() -> list:
	"""Returns the personal signup domains."""

	def generator() -> list:
		mail_settings = frappe.get_doc("Mail Settings")
		principals = [d.principal for d in mail_settings.personal_signup_domains]
		return frappe.db.get_all(
			"Mail Principal Binding", {"name": ["in", principals]}, pluck="principal_name"
		)

	return frappe.cache.hget("mail-settings", "personal_signup_domains", generator)


def get_cluster_for_tenant(tenant: str) -> str | None:
	"""Returns the cluster for the tenant."""

	def generator() -> str | None:
		return frappe.db.get_value("Mail Tenant", tenant, "cluster")

	return frappe.cache.hget(f"tenant|{tenant}", "cluster", generator)


def get_tenant_for_domain(domain_name: str) -> str | None:
	"""Returns the tenant for the domain."""

	def generator() -> str | None:
		return get_principal_tenant(domain_name, raise_exception=False)

	return frappe.cache.hget(f"domain|{domain_name}", "tenant", generator)


def get_tenant_for_user(user: str) -> str | None:
	"""Returns the tenant of the user."""

	def generator() -> str | None:
		return frappe.db.get_value("Mail Tenant Member", user, "tenant")

	return frappe.cache.hget(f"user|{user}", "tenant", generator)


def get_account_for_user(user: str) -> str | None:
	"""Returns the account of the user."""

	def generator() -> str | None:
		return frappe.db.get_value("User", user, "jmap_username")

	return frappe.cache.hget(f"user|{user}", "account", generator)


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
