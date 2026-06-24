from urllib.parse import unquote

import frappe
from frappe import _
from frappe.utils import random_string

from mail.client.doctype.mail_message.mail_message import enqueue_fetch_changes
from mail.client.doctype.push_subscription.push_subscription import (
	decrypt_jmap_push_payload,
	get_push_subscription_keys,
	is_jmap_push_notifications_frozen,
	verify_push_subscription,
)
from mail.jmap import invalidate_jmap_identities_cache, invalidate_jmap_mailboxes_cache
from mail.utils.logger import get_push_logger


@frappe.whitelist(methods=["POST"], allow_guest=True)
def push_notification() -> dict:
	"""Handle JMAP Push Notification."""

	ctx = {
		"req_id": random_string(10),
		"ip": frappe.request.remote_addr,
	}
	logger = get_push_logger(ctx)

	try:
		logger.debug("push-received")

		user = frappe.request.args.get("user") or frappe.request.args.get("account")
		if not user:
			logger.warning("missing-user")
			return {"status": "error", "message": _("Missing user query parameter.")}

		user = unquote(user)
		ctx["user"] = user

		if is_jmap_push_notifications_frozen(user):
			logger.warning("push-frozen")
			return {
				"status": "frozen",
				"message": _("Push notifications are currently frozen for this user."),
			}

		keys = get_push_subscription_keys()
		content_encoding = frappe.request.headers.get("Content-Encoding", "")

		if keys:
			logger.debug("encrypted-payload-expected")

			if content_encoding != "aes128gcm":
				logger.warning("invalid-content-encoding", encoding=content_encoding)
				return {
					"status": "error",
					"message": _("Invalid Content-Encoding. Expected 'aes128gcm'."),
				}

			logger.debug("decrypting-payload")
			request_data = decrypt_jmap_push_payload(frappe.request.get_data())
		else:
			logger.debug("using-plain-json-payload")
			request_data = frappe.request.get_json()

		event_type = request_data.get("@type")
		ctx["type"] = event_type
		logger.debug("push-type-received")

		if event_type == "PushVerification":
			logger.info("verifying-subscription")

			verify_push_subscription(
				user,
				request_data["pushSubscriptionId"],
				request_data["verificationCode"],
			)

			logger.info("subscription-verified")
			return {"status": "verified"}

		elif event_type == "StateChange":
			logger.debug("state-change-received")

			for account_id, changes in request_data.get("changed", {}).items():
				account = f"{user}:{account_id}"
				ctx["account"] = account

				for entity, state in changes.items():
					if entity == "Email":
						logger.debug("queueing-email-sync", entity=entity, state=state)
						enqueue_fetch_changes(account, state, ctx=ctx)

					elif entity == "Mailbox":
						logger.debug("invalidating-mailbox-cache", entity=entity, state=state)
						invalidate_jmap_mailboxes_cache(account_id)

					elif entity == "Identity":
						logger.debug("invalidating-identity-cache", entity=entity, state=state)
						invalidate_jmap_identities_cache(account_id)

					else:
						logger.warning("unhandled-state-change-entity", entity=entity)

				return {"status": "processed"}

		else:
			logger.warning("unknown-push-type")
			return {
				"status": "error",
				"message": _("Invalid Push Notification @type = {0}").format(event_type),
			}

	except Exception:
		logger.exception("failed-to-process", traceback=frappe.get_traceback())
		return {"status": "error", "message": _("Failed to handle JMAP Push Notification.")}
