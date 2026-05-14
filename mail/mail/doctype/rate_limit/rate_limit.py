# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class RateLimit(Document):
	def validate(self) -> None:
		self.validate_method_path()
		self.validate_key_or_ip_based()
		self.validate_methods()
		self.validate_allowed_and_blocked_ips()

	def on_update(self) -> None:
		self.clear_cache()

	def on_trash(self) -> None:
		self.clear_cache()

	def validate_method_path(self) -> None:
		"""Validate the method has the dynamic rate limit decorator"""

		fn = frappe.get_attr(self.method_path)
		if not getattr(fn, "_is_dynamic_rate_limited", False):
			frappe.throw(
				_(
					"The method {method} is missing the required {decorator} decorator. "
					"Please add it to enforce dynamic rate limiting."
				).format(
					decorator="<code>@dynamic_rate_limit</code>", method=f"<code>{self.method_path}</code>"
				)
			)

	def validate_key_or_ip_based(self) -> None:
		"""Validate key_ or IP based"""

		if not self.key_ and not self.ip_based:
			frappe.throw(_("Either key or IP flag is required."))

	def validate_methods(self) -> None:
		"""Validate methods"""

		methods = []
		if self.methods:
			for method in self.methods.split("\n"):
				if method and method not in methods:
					methods.append(method)
		self.methods = "\n".join(methods)

	def validate_allowed_and_blocked_ips(self) -> None:
		"""Validate allowed and blocked IPs"""

		allowed_and_blocked_ips = []
		for ip_type in ["allowed_ips", "blocked_ips"]:
			ips = []
			if getattr(self, ip_type):
				for ip in getattr(self, ip_type).split("\n"):
					if ip and ip not in ips:
						if ip in allowed_and_blocked_ips:
							frappe.throw(_("{0} cannot be both allowed and blocked.").format(frappe.bold(ip)))
						ips.append(ip)
						allowed_and_blocked_ips.append(ip)
			setattr(self, ip_type, "\n".join(ips))

	def clear_cache(self) -> None:
		"""Clear cache for the rate limit"""

		frappe.cache.hdel("rate_limits", self.method_path)


def create_rate_limit(
	method_path: str,
	limit: int = 5,
	seconds: int = 86_400,
	key: str | None = None,
	ip_based: bool = True,
	methods: str = "ALL",
	ignore_in_developer_mode: bool = True,
) -> "RateLimit":
	"""Create a Rate Limit document"""

	doc = frappe.new_doc("Rate Limit")
	doc.enabled = 1
	doc.ignore_in_developer_mode = cint(ignore_in_developer_mode)
	doc.method_path = method_path
	doc.methods = methods
	doc.key_ = key
	doc.limit = limit
	doc.seconds = seconds
	doc.ip_based = cint(ip_based)
	doc.insert(ignore_permissions=True)


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


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Rate Limit", ["method_path", "key_", "ip_based", "seconds"], constraint_name="unique_rate_limit"
	)
