import time

import frappe

from mail.jmap import get_push_subscription_service


def execute() -> None:
	if not frappe.utils.get_url().startswith("https://"):
		return

	for user in frappe.db.get_all("User Settings", {"username": ["!=", ""]}, pluck="name"):
		try:
			service = get_push_subscription_service(user, ignore_permissions=True)

			subscriptions = service.get()
			if ids := [s["id"] for s in subscriptions]:
				service.delete(ids)

			ps = frappe.new_doc("Push Subscription")
			ps.user = user
			ps.insert(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(
				title="Push Subscription Creation Failed",
				message=f"Failed to create push subscription for user {user}: {e!s}",
			)

		time.sleep(0.1)
