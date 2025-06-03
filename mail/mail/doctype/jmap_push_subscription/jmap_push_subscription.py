# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from contextlib import suppress

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import IfNull, Now
from uuid_utils import uuid7

from mail.jmap import get_jmap_client
from mail.utils import generate_uuid_style_hash
from mail.utils.cache import get_cluster_for_tenant
from mail.utils.dt import parse_iso_datetime


class JMAPPushSubscription(Document):
	@staticmethod
	def verify_push_subscription(account: str, subscription_id: str, verification_code: str) -> None:
		"""Verifies a push subscription using the provided verification code."""

		if not account or not subscription_id or not verification_code:
			frappe.throw(_("Invalid parameters for push subscription verification."))

		subscription_name = frappe.db.get_value(
			"JMAP Push Subscription", {"account": account, "subscription_id": subscription_id}, "name"
		)

		if not subscription_name:
			frappe.throw(
				_("No push subscription found for the given account ({0}) and subscription ID ({1}).").format(
					frappe.bold(account), frappe.bold(subscription_id)
				)
			)

		subscription = frappe.get_doc("JMAP Push Subscription", subscription_name)

		if subscription.verified:
			frappe.throw(_("Subscription already verified."))
		elif subscription.subscription_id != subscription_id:
			frappe.throw(_("Invalid subscription ID."))

		client = get_jmap_client(account, subscription.server, cache=False)
		response = client.push_subscription_set_verification_code(subscription_id, verification_code)

		kwargs = {"_verification_response": json.dumps(response)}
		if response[0][1].get("updated"):
			kwargs.update(
				{
					"status": "Active",
					"verified": 1,
					"verified_at": frappe.utils.now(),
				}
			)
		elif response[0][1].get("notUpdated"):
			kwargs["status"] = "Failed to Verify"

		subscription._db_set(notify=True, **kwargs)

	@staticmethod
	def get_push_subscriptions(account: str) -> list[dict]:
		"""Returns a list of push subscriptions for the given account."""

		try:
			client = get_jmap_client(account)
			return client.push_subscription_get()
		except Exception:
			frappe.log_error(
				title=_("Failed to get push subscriptions"),
				message=frappe.get_traceback(with_context=True),
			)
			frappe.throw(_("Failed to get push subscriptions."))

	@staticmethod
	def destroy_push_subscriptions(
		account: str, server: str | None, subscription_ids: list[str] | None = None
	) -> None:
		"""Destroys the push subscriptions for the given account."""

		try:
			client = get_jmap_client(account, server, cache=False)

			if not subscription_ids:
				subscription_ids = []
				for subscription in client.push_subscription_get():
					subscription_ids.append(subscription["id"])

			client.push_subscription_set_destroy(subscription_ids)
		except Exception:
			frappe.log_error(
				title=_("Failed to destroy push subscription(s)"),
				message=frappe.get_traceback(with_context=True),
			)
			frappe.throw(_("Failed to destroy push subscription(s)."))

	@property
	def verification_response(self) -> str | None:
		"""Returns the indented JSON verification response."""

		return (
			json.dumps(json.loads(self._verification_response), indent=4)
			if self._verification_response
			else None
		)

	@property
	def renew_response(self) -> str | None:
		"""Returns the indented JSON renew response."""

		return json.dumps(json.loads(self._renew_response), indent=4) if self._renew_response else None

	@property
	def subscription_response(self) -> str | None:
		"""Returns the indented JSON subscription response."""

		return (
			json.dumps(json.loads(self._subscription_response), indent=4)
			if self._subscription_response
			else None
		)

	def autoname(self) -> None:
		self.name = str(uuid7())

	def before_insert(self) -> None:
		self.set_endpoint()

	def validate(self) -> None:
		self.validate_server()

	def after_insert(self) -> None:
		self._subscribe()

	def on_trash(self) -> None:
		if self.subscription_id:
			JMAPPushSubscription.destroy_push_subscriptions(self.account, self.server, [self.subscription_id])

	def set_endpoint(self) -> None:
		"""Sets the endpoint URL for the push subscription."""

		if not self.endpoint:
			self.endpoint = (
				f"{frappe.utils.get_url()}/api/method/mail.api.jmap.push_notification?account={self.account}"
			)

	def validate_server(self) -> None:
		"""Validates that the server and account belong to the same cluster."""

		account_tenant = frappe.db.get_value("Mail Account", self.account, "tenant")
		server_cluster = frappe.db.get_value("Mail Server", self.server, "cluster")

		if server_cluster != get_cluster_for_tenant(account_tenant):
			frappe.throw(
				_("The Mail Server {0} does not belong to the same cluster as the account {1}.").format(
					frappe.bold(self.server), frappe.bold(self.account)
				)
			)

	def _subscribe(self) -> None:
		"""Subscribes to the JMAP push subscription."""

		kwargs = {
			"verified": 0,
			"verified_at": None,
			"expires_at": None,
			"subscription_id": None,
			"_verification_response": None,
			"_renew_response": None,
		}
		device_client_id = generate_uuid_style_hash(
			f"frappe-{frappe.local.site.replace('.', '-')}-{self.account}"
		)
		types = self.notification_types.split("\n") if self.notification_types else None

		try:
			client = get_jmap_client(self.account, self.server, cache=False)
			response = client.push_subscription_create(self.name, device_client_id, self.endpoint, types)

			kwargs["_subscription_response"] = json.dumps(response)
			if response.get("created"):
				kwargs.update(
					{
						"status": "Pending Verification",
						"expires_at": parse_iso_datetime(response["created"][self.name]["expires"]),
						"subscription_id": response["created"][self.name]["id"],
					}
				)
			else:
				frappe.throw(_("Failed to subscribe to JMAP Push Subscription."))

			self._db_set(**kwargs)
		except Exception:
			frappe.log_error(
				title=_("Failed to subscribe to JMAP Push Subscription"),
				message=frappe.get_traceback(with_context=True),
			)
			kwargs["status"] = "Failed to Subscribe"
			self._db_set(**kwargs)

	@frappe.whitelist()
	def renew(self) -> None:
		"""Renews the JMAP push subscription."""

		if not self.verified or not self.subscription_id:
			frappe.throw(_("Cannot renew a non-verified subscription."))
		elif self.status not in ["Active", "Expired", "Failed to Renew"]:
			frappe.throw(_("Cannot renew a subscription that is not active or expired."))

		try:
			client = get_jmap_client(self.account, self.server, cache=False)
			response = client.push_subscription_set_expires(self.subscription_id)

			kwargs = {"_renew_response": json.dumps(response)}
			if response[0][1].get("updated"):
				new_expires = parse_iso_datetime(response[1][1]["list"][0]["expires"])

				if new_expires == self.expires_at:
					kwargs["status"] = "Failed to Renew"
				else:
					kwargs.update(
						{
							"status": "Active",
							"expires_at": new_expires,
						}
					)
			elif response[0][1].get("notUpdated"):
				kwargs["status"] = "Failed to Renew"
			else:
				frappe.throw(_("Failed to renew JMAP Push Subscription."))

			self._db_set(**kwargs)
		except Exception:
			frappe.log_error(
				title=_("Failed to renew push subscription"),
				message=frappe.get_traceback(with_context=True),
			)
			frappe.throw(_("Failed to renew push subscription."))

	@frappe.whitelist()
	def resubscribe(self) -> None:
		"""Resubscribes to the JMAP push subscription."""

		if self.status not in [
			"Expired",
			"Failed to Verify",
			"Failed to Renew",
			"Failed to Subscribe",
			"Pending Verification",
		]:
			frappe.throw(_("Cannot resubscribe a subscription that is not expired or failed."))

		if self.subscription_id:
			JMAPPushSubscription.destroy_push_subscriptions(self.account, self.server, [self.subscription_id])

		self._subscribe()

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


def create_jmap_push_subscriptions(account: str) -> list["JMAPPushSubscription"]:
	"""Creates JMAP Push Subscriptions for the given account if they do not already exist."""

	account_tenant = frappe.db.get_value("Mail Account", account, "tenant")
	account_cluster = get_cluster_for_tenant(account_tenant)

	if not account_cluster:
		frappe.throw(_("No cluster found for the account {0}.").format(frappe.bold(account)))

	servers = frappe.db.get_all("Mail Server", {"enabled": 1, "cluster": account_cluster}, pluck="name")

	subscriptions = []
	for server in servers:
		subscription = create_jmap_push_subscription(account, server)
		subscriptions.append(subscription)

	return subscriptions


def create_jmap_push_subscription(account: str, server: str) -> "JMAPPushSubscription":
	"""Creates a JMAP Push Subscription for the given account and server."""

	if subscription := frappe.db.get_value(
		"JMAP Push Subscription", {"account": account, "server": server}, "name"
	):
		return frappe.get_doc("JMAP Push Subscription", subscription)

	push_subscription = frappe.new_doc("JMAP Push Subscription")
	push_subscription.account = account
	push_subscription.server = server
	push_subscription.insert(ignore_permissions=True)

	return push_subscription


def delete_jmap_push_subscriptions(account: str) -> None:
	"""Deletes all JMAP Push Subscriptions for the given account."""

	for subscription in frappe.db.get_all("JMAP Push Subscription", {"account": account}, pluck="name"):
		frappe.delete_doc("JMAP Push Subscription", subscription, ignore_permissions=True)


def renew_push_subscriptions() -> None:
	"""Renews push subscriptions that are about to expire within the next 2 days."""

	PS = frappe.qb.DocType("JMAP Push Subscription")
	subscriptions = (
		frappe.qb.from_(PS)
		.select(PS.name)
		.where(
			(PS.verified == 1)
			& (IfNull(PS.subscription_id, "") != "")
			& (PS.expires_at < (Now() + Interval(days=2)))
			& (PS.status.isin(["Active", "Expired", "Failed to Renew"]))
		)
	).run(pluck="name")

	if not subscriptions:
		return

	for subscription in subscriptions:
		with suppress(Exception):
			push_subscription = frappe.get_doc("JMAP Push Subscription", subscription)
			push_subscription.renew()


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"JMAP Push Subscription", ["account", "server"], constraint_name="unique_push_subscription"
	)
