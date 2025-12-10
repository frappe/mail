from urllib.parse import unquote

import frappe
from frappe import _

from mail.client.doctype.mail_message.mail_message import enqueue_fetch_changes
from mail.client.doctype.push_subscription.push_subscription import (
	is_jmap_push_notifications_frozen,
	verify_push_subscription,
)
from mail.jmap import invalidate_jmap_identities_cache, invalidate_jmap_mailboxes_cache


@frappe.whitelist(methods=["POST"], allow_guest=True)
def push_notification() -> dict:
	"""Handle JMAP Push Notification."""

	try:
		user = frappe.request.args.get("user")
		if not user:
			frappe.throw(_("Missing user query parameter."))

		user = unquote(user)
		request_data = frappe.request.get_json()

		if request_data["@type"] == "PushVerification":
			verify_push_subscription(
				user, request_data["pushSubscriptionId"], request_data["verificationCode"]
			)
			return {}
		elif request_data["@type"] == "StateChange":
			changes = []
			for change in request_data["changed"].values():
				changes.append(change)

			for change in changes:
				for key, state in change.items():
					if key == "Email":
						if not is_jmap_push_notifications_frozen(user):
							enqueue_fetch_changes(user, state)
					elif key == "Mailbox":
						invalidate_jmap_mailboxes_cache(user)
					elif key == "Identity":
						invalidate_jmap_identities_cache(user)

			return {}
		else:
			frappe.throw(_("Invalid Push Notification @type = {0}").format(request_data["@type"]))
	except Exception:
		frappe.log_error(
			title=_("Failed to handle JMAP Push Notification"),
			message=frappe.get_traceback(with_context=True),
		)
		return {"status": "error", "message": _("Failed to handle JMAP Push Notification.")}
