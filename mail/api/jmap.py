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


@frappe.whitelist(methods=["POST"], allow_guest=True)
def push_notification() -> dict:
	"""Handle JMAP Push Notification."""

	logger = frappe.logger("mail.push", allow_site=True, file_count=100)
	logger.setLevel("DEBUG")

	ctx = {
		"req_id": random_string(10),
		"ip": frappe.request.remote_addr,
	}

	try:
		logger.info({**ctx, "event": "received"})

		user = frappe.request.args.get("user") or frappe.request.args.get("account")
		if not user:
			logger.error({**ctx, "event": "missing-user"})
			return {"status": "error", "message": _("Missing user query parameter.")}

		user = unquote(user)
		ctx["user"] = user

		logger.info({**ctx, "event": "processing"})

		if is_jmap_push_notifications_frozen(user):
			logger.warning({**ctx, "event": "frozen"})
			return {
				"status": "frozen",
				"message": _("Push notifications are currently frozen for this user."),
			}

		keys = get_push_subscription_keys()
		content_encoding = frappe.request.headers.get("Content-Encoding", "")

		if keys:
			logger.debug({**ctx, "event": "encrypted-payload-expected"})

			if content_encoding != "aes128gcm":
				logger.error({**ctx, "encoding": content_encoding, "event": "invalid-content-encoding"})
				return {
					"status": "error",
					"message": _("Invalid Content-Encoding. Expected 'aes128gcm'."),
				}

			logger.debug({**ctx, "event": "decrypting-payload"})
			request_data = decrypt_jmap_push_payload(frappe.request.get_data())
		else:
			logger.debug({**ctx, "event": "using-plain-json-payload"})
			request_data = frappe.request.get_json()

		event_type = request_data.get("@type")
		logger.debug({**ctx, "type": event_type, "event": "push-type-received"})

		if event_type == "PushVerification":
			logger.info({**ctx, "type": event_type, "event": "verifying-subscription"})

			verify_push_subscription(
				user,
				request_data["pushSubscriptionId"],
				request_data["verificationCode"],
			)

			logger.info({**ctx, "type": event_type, "event": "subscription-verified"})
			return {"status": "verified"}

		elif event_type == "StateChange":
			logger.info({**ctx, "type": event_type, "event": "state-change-received"})

			changes = [c for c in request_data.get("changed", {}).values()]

			for change in changes:
				for entity, state in change.items():
					if entity == "Email":
						logger.info(
							{
								**ctx,
								"type": event_type,
								"entity": entity,
								"state": state,
								"event": "queueing-email-sync",
							}
						)
						enqueue_fetch_changes(user, state)

					elif entity == "Mailbox":
						logger.info(
							{
								**ctx,
								"type": event_type,
								"entity": entity,
								"state": state,
								"event": "invalidating-mailbox-cache",
							}
						)
						invalidate_jmap_mailboxes_cache(user)

					elif entity == "Identity":
						logger.info(
							{
								**ctx,
								"type": event_type,
								"entity": entity,
								"state": state,
								"event": "invalidating-identity-cache",
							}
						)
						invalidate_jmap_identities_cache(user)

					else:
						logger.debug(
							{
								**ctx,
								"type": event_type,
								"entity": entity,
								"event": "unhandled-state-change-entity",
							}
						)

			return {"status": "processed"}

		else:
			logger.error({**ctx, "type": event_type, "event": "unknown-push-type"})
			return {
				"status": "error",
				"message": _("Invalid Push Notification @type = {0}").format(event_type),
			}

	except Exception:
		logger.exception({**ctx, "event": "failed-to-process", "traceback": frappe.get_traceback()})
		return {"status": "error", "message": _("Failed to handle JMAP Push Notification.")}
