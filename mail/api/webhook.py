# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Webhook API endpoint for receiving notifications from Stalwart Mail Server.

This module handles webhook events from Stalwart for:
- Scheduled email delivery (FUTURERELEASE)
- Message ingestion
- Queue events (rescheduled, cancelled, etc.)

When a scheduled email is delivered, Stalwart sends a webhook notification which triggers
the update of the email status from "Scheduled" to "Sent".
"""

import base64
import hashlib
import hmac

import frappe
from frappe import _

# Events that indicate email was delivered
DELIVERY_EVENTS = (
	"delivery.completed",
	"delivery.delivered",
	"delivery.dsn-success",
)

# Events related to queue operations
QUEUE_EVENTS = (
	"queue.rescheduled",
	"queue.queue-message",
	"queue.queue-message-authenticated",
)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def delivery_status():
	"""
	Webhook endpoint for Stalwart delivery status notifications.

	Stalwart sends webhook events when emails are delivered. This endpoint
	handles delivery and queue events to update scheduled email status.

	Webhook payload format:
	{
		"events": [
			{
				"id": "12345",
				"createdAt": "2023-06-21T14:55:00Z",
				"type": "delivery.completed",
				"data": {
					"queueId": "...",
					"from": "sender@example.com",
					"to": "recipient@example.com",
					...
				}
			}
		]
	}
	"""

	# Validate webhook signature if configured
	if not _validate_webhook_signature():
		frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

	try:
		payload = frappe.request.get_json(force=True)
	except Exception:
		frappe.throw(_("Invalid JSON payload"), frappe.ValidationError)

	if not payload or "events" not in payload:
		frappe.throw(_("Invalid webhook payload: missing 'events'"), frappe.ValidationError)

	events = payload.get("events", [])
	delivery_events = []
	queue_events = []

	# Filter and categorize events
	for event in events:
		event_type = event.get("type", "")
		if event_type in DELIVERY_EVENTS:
			delivery_events.append(event)
		elif event_type in QUEUE_EVENTS:
			queue_events.append(event)

	processed = 0

	if delivery_events:
		# Process delivery events asynchronously
		frappe.enqueue(
			"mail.api.webhook.process_delivery_events",
			queue="short",
			events=delivery_events,
			enqueue_after_commit=True,
		)
		processed += len(delivery_events)

	if queue_events:
		# Process queue events asynchronously
		frappe.enqueue(
			"mail.api.webhook.process_queue_events",
			queue="short",
			events=queue_events,
			enqueue_after_commit=True,
		)
		processed += len(queue_events)

	return {"status": "ok", "processed": processed}


def _validate_webhook_signature() -> bool:
	"""
	Validate the webhook signature using HMAC.

	Stalwart sends the signature in the X-Signature header as base64-encoded HMAC.
	"""

	signature_header = frappe.request.headers.get("X-Signature")

	# If no signature header and no secret configured, allow the request
	# This supports setups without signature verification
	webhook_secret = frappe.conf.get("stalwart_webhook_secret")
	if not webhook_secret:
		return True

	if not signature_header:
		return False

	try:
		request_body = frappe.request.get_data()
		expected_signature = hmac.new(
			webhook_secret.encode("utf-8"),
			request_body,
			hashlib.sha256
		).digest()
		expected_signature_b64 = base64.b64encode(expected_signature).decode("utf-8")

		return hmac.compare_digest(signature_header, expected_signature_b64)
	except Exception:
		return False


def process_delivery_events(events: list[dict]) -> None:
	"""
	Process delivery events and update scheduled email status.

	This function is called asynchronously to process delivery notifications
	from Stalwart and update the corresponding Mail Queue entries.
	"""

	from mail.jmap import get_jmap_client

	# Collect unique queue IDs from events
	# The queueId in Stalwart corresponds to our Mail Queue name (set via ENVID)
	queue_ids = set()
	for event in events:
		data = event.get("data", {})
		# ENVID is set to our Mail Queue name during submission
		queue_id = data.get("parameters", {}).get("envid") or data.get("queueId")
		if queue_id:
			queue_ids.add(queue_id)

	if not queue_ids:
		return

	# Find scheduled emails that match these queue IDs
	scheduled_emails = frappe.get_all(
		"Mail Queue",
		filters={
			"status": "Scheduled",
			"name": ["in", list(queue_ids)],
		},
		fields=["name", "user", "id", "submission_id"],
	)

	if not scheduled_emails:
		# Try to find by submission_id as fallback
		# Sometimes the event might reference the submission ID
		return

	# Group by user for efficient JMAP calls
	user_emails = {}
	for email in scheduled_emails:
		user_emails.setdefault(email.user, []).append(email)

	for user, emails in user_emails.items():
		try:
			client = get_jmap_client(user)
			sent_mailbox_id = client.get_mailbox_id_by_role("sent", create_if_not_exists=True)

			email_ids_to_move = []
			for email in emails:
				# Update the Mail Queue status
				frappe.db.set_value(
					"Mail Queue",
					email.name,
					{
						"status": "Sent",
						"mailbox_id": sent_mailbox_id,
					},
					update_modified=False,
				)

				if email.id:
					email_ids_to_move.append(email.id)

			# Move emails from Scheduled to Sent folder in Stalwart
			if email_ids_to_move:
				client.email_update(email_ids_to_move, mailbox_id=sent_mailbox_id)

		except Exception:
			frappe.log_error(
				f"Failed to process delivery webhook for user {user}",
				frappe.get_traceback(with_context=True),
			)

	frappe.db.commit()


def process_queue_events(events: list[dict]) -> None:
	"""
	Process queue-related events from Stalwart.

	Queue events handle status changes for scheduled (FUTURERELEASE) emails:
	- queue.rescheduled: When a scheduled email's delivery time is changed
	- queue.cancelled: When a scheduled email is cancelled

	Args:
		events: List of event dictionaries from Stalwart webhook
	"""

	for event in events:
		event_type = event.get("type", "")
		data = event.get("data", {})

		# Get queue ID (message ID in Stalwart's queue)
		queue_id = data.get("queueId") or data.get("messageId")
		if not queue_id:
			continue

		try:
			# Find the corresponding Mail Queue entry
			mail_queue = frappe.db.get_value(
				"Mail Queue",
				filters={
					"status": "Scheduled",
					"queue_id": queue_id,
				},
				fieldname=["name", "user", "id", "submission_id"],
				as_dict=True,
			)

			if not mail_queue:
				# Try finding by submission_id
				mail_queue = frappe.db.get_value(
					"Mail Queue",
					filters={
						"status": "Scheduled",
						"submission_id": queue_id,
					},
					fieldname=["name", "user", "id", "submission_id"],
					as_dict=True,
				)

			if not mail_queue:
				continue

			if event_type == "queue.rescheduled":
				# Update the scheduled time in our database
				new_time = data.get("scheduledTime") or data.get("holdUntil")
				if new_time:
					# Convert timestamp to datetime if needed
					from datetime import datetime
					if isinstance(new_time, int | float):
						new_time = datetime.fromtimestamp(new_time)

					frappe.db.set_value(
						"Mail Queue",
						mail_queue.name,
						"scheduled_at",
						new_time,
						update_modified=False,
					)

					frappe.logger().info(
						f"Updated scheduled time for {mail_queue.name} to {new_time}"
					)

			elif event_type == "queue.cancelled":
				# Mark as cancelled in our database
				frappe.db.set_value(
					"Mail Queue",
					mail_queue.name,
					"status",
					"Cancelled",
					update_modified=False,
				)

				frappe.logger().info(
					f"Marked {mail_queue.name} as cancelled"
				)

		except Exception:
			frappe.log_error(
				f"Failed to process queue event {event_type}",
				frappe.get_traceback(with_context=True),
			)

	frappe.db.commit()


@frappe.whitelist(allow_guest=True, methods=["POST"])
def message_ingest():
	"""
	Webhook endpoint for Stalwart message ingest notifications.

	This endpoint handles 'message-ingest.*' events which can be used
	to trigger real-time sync of incoming emails.
	"""

	# Validate webhook signature if configured
	if not _validate_webhook_signature():
		frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

	try:
		payload = frappe.request.get_json(force=True)
	except Exception:
		frappe.throw(_("Invalid JSON payload"), frappe.ValidationError)

	if not payload or "events" not in payload:
		frappe.throw(_("Invalid webhook payload: missing 'events'"), frappe.ValidationError)

	events = payload.get("events", [])
	ingest_events = []

	# Filter for message ingest events
	for event in events:
		event_type = event.get("type", "")
		if event_type.startswith("message-ingest."):
			ingest_events.append(event)

	if ingest_events:
		# Process ingest events asynchronously
		frappe.enqueue(
			"mail.api.webhook.process_ingest_events",
			queue="short",
			events=ingest_events,
			enqueue_after_commit=True,
		)

	return {"status": "ok", "processed": len(ingest_events)}


def process_ingest_events(events: list[dict]) -> None:
	"""
	Process message ingest events for real-time email sync.

	This can be extended to trigger immediate sync for specific users
	when they receive new emails.
	"""

	# For now, just log the events
	# Future enhancement: trigger real-time sync for affected users
	for event in events:
		data = event.get("data", {})
		account_id = data.get("accountId")
		mailbox_id = data.get("mailboxId")

		if account_id:
			frappe.logger().debug(
				f"Message ingest event: account={account_id}, mailbox={mailbox_id}, type={event.get('type')}"
			)
