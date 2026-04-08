# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import base64
import json
from uuid import uuid7

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from mail.jmap import get_push_subscription_service
from mail.utils import generate_uuid_style_hash, parse_filters
from mail.utils.dt import parse_iso_datetime
from mail.utils.user import has_jmap_settings
from mail.utils.validation import has_permission_for_user


class PushSubscription(Document):
	@property
	def _types(self) -> list[str]:
		"""Returns the types of push subscriptions as a list."""

		types = []
		if self.types:
			types = json.loads(self.types)

		return types

	def db_insert(self, *args, **kwargs) -> None:
		self.id = add_push_subscription(
			self.user,
			self.device_client_id,
			self.url,
			self._types,
			ignore_permissions=bool(self.flags.ignore_permissions),
		)
		self.name = f"{self.user}|{self.id}"

	def load_from_db(self) -> "PushSubscription":
		user, id = self.name.split("|")
		subscription = get_push_subscription(user, id)
		return super(Document, self).__init__(subscription)

	def db_update(self) -> None:
		raise NotImplementedError

	def delete(self) -> None:
		user, id = self.name.split("|")
		delete_push_subscriptions(user, [id])

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		id = filters.get("id")
		user = filters.get("user") or frappe.session.user

		if not user or user in ("Guest", "Administrator"):
			frappe.msgprint(_("Please select a user to view push subscriptions."), alert=True)
			return []

		subscriptions = []
		if id:
			if subscription := get_push_subscription(user, id, raise_exception=False):
				subscriptions.append(subscription)
		else:
			subscriptions = fetch_push_subscriptions(user, limit=page_length)

		if not subscriptions:
			frappe.msgprint(_("No push subscriptions found."), alert=True)

		return subscriptions

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		user = filters.get("user") or frappe.session.user
		return (
			frappe.cache.get_value(_get_total_cache_key(user))
			if user and has_permission_for_user(user, raise_exception=False)
			else 0
		)

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	def validate(self) -> None:
		self.validate_url()

	def validate_url(self) -> None:
		"""Validates the URL to ensure it starts with 'https://'."""

		if self.url and not self.url.startswith("https"):
			frappe.throw(_("The URL must start with 'https://'."))

	@frappe.whitelist()
	def renew(self) -> None:
		"""Renews the push subscription subscription."""

		renew_push_subscription(self.user, self.id)


def _get_total_cache_key(user: str) -> str:
	"""Returns a cache key for total push subscriptions count for the given user."""

	return f"{user}:push_subscriptions:total"


@frappe.whitelist()
def bulk_delete(names: str | list[str]) -> None:
	"""Deletes multiple push subscriptions given their names."""

	if isinstance(names, str):
		names = json.loads(names)

	user_ids_map = {}
	for name in names:
		user, id = name.split("|")
		user_ids_map.setdefault(user, []).append(id)

	for user, ids in user_ids_map.items():
		delete_push_subscriptions(user, ids)

	frappe.msgprint(_("Push Subscriptions deleted successfully."), alert=True)


@frappe.whitelist()
def add_push_subscription(
	user: str,
	device_client_id: str | None = None,
	url: str | None = None,
	types: list[str] | None = None,
	ignore_permissions: bool = False,
) -> str:
	"""Adds a push subscription subscription for the given user and returns the subscription ID."""

	if not ignore_permissions:
		has_permission_for_user(user)

	device_client_id = device_client_id or generate_uuid_style_hash(
		f"frappe-{frappe.local.site.replace('.', '-')}-{user}"
	)
	url = url or f"{frappe.utils.get_url()}/api/method/mail.api.jmap.push_notification?user={user}"
	types = types or None

	creation_id = str(uuid7())
	push_subscription = {
		"creation_id": creation_id,
		"device_client_id": device_client_id,
		"url": url,
		"types": types,
		"keys": get_push_subscription_keys(),
	}

	service = get_push_subscription_service(user, ignore_permissions=ignore_permissions)
	response = service.create([push_subscription])

	title = _("Push Subscription Creation Error")
	if response.get("created"):
		return response["created"][creation_id]["id"]
	elif response.get("notCreated"):
		frappe.throw(_(response["notCreated"][creation_id]["description"]), title=title)
	else:
		frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def get_push_subscription(user: str, id: str, raise_exception: bool = True) -> dict | None:
	"""Returns push subscription details for the given name in the format 'user|id'."""

	has_permission_for_user(user)

	service = get_push_subscription_service(user)
	if subscriptions := service.get([id]):
		return format_push_subscription(user, subscriptions[0])

	if raise_exception:
		frappe.throw(
			_("Push Subscription with ID {0} not found in user {1}.").format(
				frappe.bold(id), frappe.bold(user)
			),
			title=_("Push Subscription Not Found"),
		)


def verify_push_subscription(user: str, id: str, verification_code: str) -> None:
	"""Verifies a push subscription for the given user, subscription ID, and verification code."""

	if not frappe.db.exists("User", {"name": user, "enabled": 1}):
		frappe.throw(_("User does not exist or is disabled."))

	has_jmap_settings(user, raise_exception=True)

	push_subscription = {"id": id, "verification_code": verification_code}

	service = get_push_subscription_service(user, ignore_permissions=True)
	response = service.update([push_subscription])

	title = _("Push Subscription Renewal Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def renew_push_subscription(user: str, id: str) -> None:
	"""Renews a push subscription subscription for the given user and subscription ID."""

	has_permission_for_user(user)

	service = get_push_subscription_service(user)
	response = service.update([{"id": id}])

	title = _("Push Subscription Renewal Error")
	if not response.get("updated"):
		if response.get("notUpdated"):
			frappe.throw(_(response["notUpdated"][id]["description"]), title=title)
		else:
			frappe.throw(_(response["description"]), title=title)


@frappe.whitelist()
def delete_push_subscriptions(user: str, ids: list[str]) -> None:
	"""Deletes push subscriptions for the given user and list of subscription IDs."""

	has_permission_for_user(user)

	service = get_push_subscription_service(user)
	response = service.delete(ids)

	if response.get("notDestroyed"):
		error_messages = []
		for id, error in response["notDestroyed"].items():
			error_messages.append(f"{id}: {error['description']}")
		frappe.throw(
			_("Push Subscription Deletion Error(s):<br>{0}").format("<br>".join(error_messages)),
			title=_("Push Subscription Deletion Error"),
		)


@frappe.whitelist()
def fetch_push_subscriptions(user: str, page: int = 1, limit: int = 10) -> list:
	"""Fetches push subscriptions for the given user with pagination."""

	has_permission_for_user(user)

	service = get_push_subscription_service(user)
	subscriptions = service.get()
	formatted_subscriptions = [format_push_subscription(user, sub) for sub in subscriptions]
	frappe.cache.set_value(_get_total_cache_key(user), len(subscriptions), expires_in_sec=600)

	start = (page - 1) * limit
	end = start + limit

	return formatted_subscriptions[start:end]


def format_push_subscription(user: str, push_subscription: dict) -> dict:
	"""Formats push subscription data for display."""

	expires = parse_iso_datetime(push_subscription["expires"]) if push_subscription.get("expires") else None
	types = push_subscription.get("types") or []
	return {
		"user": user,
		"id": push_subscription["id"],
		"name": f"{user}|{push_subscription['id']}",
		"device_client_id": push_subscription["deviceClientId"],
		"expires": expires,
		"types": json.dumps(types, indent=4),
		"creation": today(),
		"modified": today(),
	}


def get_push_subscription_keys() -> dict | None:
	"""Returns the JMAP push subscription encryption keys from Mail Settings, or None if not configured."""

	settings = frappe.get_cached_doc("Mail Settings")
	p256dh = (settings.get("jmap_push_p256dh") or "").strip()
	auth = (settings.get_password("jmap_push_auth") if settings.get("jmap_push_auth") else "").strip()

	if p256dh and auth:
		return {"p256dh": p256dh, "auth": auth}


def decrypt_jmap_push_payload(raw_body: bytes) -> dict:
	"""Decrypts the JMAP push notification payload using the encryption keys from Mail Settings and returns the decrypted data as a dictionary."""

	import struct

	from cryptography.hazmat.primitives.asymmetric import ec
	from cryptography.hazmat.primitives.asymmetric.ec import ECDH
	from cryptography.hazmat.primitives.ciphers.aead import AESGCM
	from cryptography.hazmat.primitives.hashes import SHA256
	from cryptography.hazmat.primitives.kdf.hkdf import HKDF
	from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

	def _b64decode(s: str) -> bytes:
		s = s.strip()
		return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

	settings = frappe.get_cached_doc("Mail Settings")

	private_key_b64 = (
		settings.get_password("jmap_push_private_key") if settings.get("jmap_push_private_key") else ""
	).strip()

	auth_b64 = (settings.get_password("jmap_push_auth") if settings.get("jmap_push_auth") else "").strip()

	if not private_key_b64 or not auth_b64:
		frappe.throw(_("JMAP Push Subscription decryption keys are not configured in Mail Settings."))

	try:
		auth_bytes = _b64decode(auth_b64)
		priv_bytes = _b64decode(private_key_b64)
	except Exception:
		frappe.throw(_("Invalid base64 encoding in JMAP push keys."))

	if len(priv_bytes) != 32:
		frappe.throw(_("Invalid JMAP push private key length (must be 32 bytes)."))

	try:
		private_key = ec.derive_private_key(int.from_bytes(priv_bytes, "big"), ec.SECP256R1())
	except Exception:
		frappe.throw(_("Failed to construct EC private key."))

	if len(raw_body) < 21:
		frappe.throw(_("Encrypted push payload is too short."))

	salt = raw_body[:16]
	rs = struct.unpack_from(">I", raw_body, 16)[0]
	idlen = raw_body[20]

	if rs <= 0:
		frappe.throw(_("Invalid record size in encrypted payload."))

	if len(raw_body) < 21 + idlen:
		frappe.throw(_("Malformed encrypted payload (invalid key length)."))

	sender_pub_bytes = raw_body[21 : 21 + idlen]
	ciphertext_data = raw_body[21 + idlen :]

	if not ciphertext_data:
		frappe.throw(_("Encrypted payload missing ciphertext data."))

	try:
		sender_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), sender_pub_bytes)
	except Exception:
		frappe.throw(_("Invalid sender public key in encrypted payload."))

	try:
		shared_secret = private_key.exchange(ECDH(), sender_pub)
	except Exception:
		frappe.throw(_("ECDH key exchange failed."))

	receiver_pub_bytes = private_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)

	auth_info = b"WebPush: info\x00" + receiver_pub_bytes + sender_pub_bytes

	try:
		ikm = HKDF(
			algorithm=SHA256(),
			length=32,
			salt=auth_bytes,
			info=auth_info,
		).derive(shared_secret)

		cek = HKDF(
			algorithm=SHA256(),
			length=16,
			salt=salt,
			info=b"Content-Encoding: aes128gcm\x00",
		).derive(ikm)

		nonce_base = HKDF(
			algorithm=SHA256(),
			length=12,
			salt=salt,
			info=b"Content-Encoding: nonce\x00",
		).derive(ikm)
	except Exception:
		frappe.throw(_("Key derivation failed."))

	if len(nonce_base) != 12:
		frappe.throw(_("Invalid nonce base length derived."))

	aesgcm = AESGCM(cek)

	plaintext = bytearray()
	seq = 0
	pos = 0

	MAX_PLAINTEXT_SIZE = 1024 * 1024

	while pos < len(ciphertext_data):
		record = ciphertext_data[pos : pos + rs]
		pos += rs

		if not record:
			break

		# Nonce = nonce_base XOR seq (12 bytes)
		seq_bytes = seq.to_bytes(12, "big")
		nonce = bytes(a ^ b for a, b in zip(nonce_base, seq_bytes, strict=False))

		try:
			decrypted = aesgcm.decrypt(nonce, record, None)
		except Exception:
			frappe.throw(_("Failed to decrypt push payload (authentication failed)."))

		i = len(decrypted) - 1
		while i >= 0 and decrypted[i] == 0x00:
			i -= 1

		if i < 0:
			frappe.throw(_("Invalid padding in decrypted record."))

		pad_delimiter = decrypted[i]
		if pad_delimiter not in (0x01, 0x02):
			frappe.throw(_("Invalid padding delimiter in decrypted record."))

		plaintext.extend(decrypted[:i])

		if len(plaintext) > MAX_PLAINTEXT_SIZE:
			frappe.throw(_("Decrypted payload exceeds maximum allowed size."))

		seq += 1

	try:
		return json.loads(bytes(plaintext))
	except json.JSONDecodeError:
		frappe.throw(_("Decrypted push payload is not valid JSON."))


def freeze_jmap_push_notifications(user: str) -> None:
	"""Freezes JMAP push notifications for the given user."""

	frappe.cache.hset("frozen_jmap_push_notifications", user, True)


def unfreeze_jmap_push_notifications(user: str) -> None:
	"""Unfreezes JMAP push notifications for the given user."""

	frappe.cache.hdel("frozen_jmap_push_notifications", user)


def is_jmap_push_notifications_frozen(user: str) -> bool:
	"""Returns True if JMAP push notifications are frozen for the given user."""

	return frappe.cache.hget("frozen_jmap_push_notifications", user) is True


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Push Subscription":
		return False

	return has_permission_for_user(doc.user, raise_exception=False)
