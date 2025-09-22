from urllib.parse import unquote

import frappe
from frappe import _

from mail.jmap import invalidate_jmap_identities_cache, invalidate_jmap_mailboxes_cache
from mail.mail.doctype.jmap_push_subscription.jmap_push_subscription import (
	JMAPPushSubscription,
	is_jmap_push_notifications_frozen,
)
from mail.mail.doctype.mail_message.mail_message import enqueue_fetch_changes


@frappe.whitelist(methods=["POST"], allow_guest=True)
def push_notification() -> dict:
	"""Handle JMAP Push Notification."""

	try:
		account = frappe.request.args.get("account")
		if not account:
			frappe.throw(_("Missing account query parameter."))

		account = unquote(account)
		request_data = frappe.request.get_json()

		if request_data["@type"] == "PushVerification":
			JMAPPushSubscription.verify_push_subscription(
				account, request_data["pushSubscriptionId"], request_data["verificationCode"]
			)
			return {}
		elif request_data["@type"] == "StateChange":
			changes = []
			for change in request_data["changed"].values():
				changes.append(change)

			for change in changes:
				for key, state in change.items():
					if key == "Email":
						if not is_jmap_push_notifications_frozen(account):
							enqueue_fetch_changes(account, state)
					elif key == "Mailbox":
						invalidate_jmap_mailboxes_cache(account)
					elif key == "Identity":
						invalidate_jmap_identities_cache(account)

			return {}
		else:
			frappe.throw(_("Invalid Push Notification @type = {0}").format(request_data["@type"]))
	except Exception:
		frappe.log_error(
			title=_("Failed to handle JMAP Push Notification"),
			message=frappe.get_traceback(with_context=True),
		)
		return {"status": "error", "message": _("Failed to handle JMAP Push Notification.")}
