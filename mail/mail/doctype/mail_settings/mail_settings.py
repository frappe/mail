# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import base64
import os

import frappe
from frappe import _
from frappe.model.document import Document

from mail.server.doctype.dns_record.dns_record import get_dns_provider


class MailSettings(Document):
	def validate(self) -> None:
		self.validate_root_domain_name()
		self.validate_dns_provider()
		self.validate_jmap_push_subscription_keys()
		self.validate_signup_domains()

	def on_update(self) -> None:
		self.clear_cache()

		if self.has_value_changed("root_domain_name"):
			self.handle_root_domain_change()

	def validate_root_domain_name(self) -> None:
		"""Validates the Root Domain Name."""

		if self.root_domain_name:
			self.root_domain_name = self.root_domain_name.lower()

	def validate_dns_provider(self) -> None:
		"""Validates the DNS Provider."""

		if not self.dns_provider:
			return

		if not self.root_domain_name:
			frappe.throw(_("Please set the Root Domain Name before configuring the DNS Provider."))

		match self.dns_provider:
			case "AmazonRoute53":
				if not self.dns_provider_access_key or not self.dns_provider_access_secret:
					frappe.throw(_("Please set the DNS Provider Access Key and Secret."))

			case "DigitalOcean" | "Cloudflare" | "Hetzner" | "Linode" | "Namecheap":
				if not self.dns_provider_token:
					frappe.throw(_("Please set the DNS Provider Token."))
				elif self.dns_provider == "Namecheap":
					if not self.dns_provider_username or not self.dns_provider_client_ip:
						frappe.throw(_("Please set the DNS Provider Username and Client IP."))

			case "GoDaddy":
				if not self.dns_provider_key or not self.dns_provider_secret:
					frappe.throw(_("Please set the DNS Provider Key and Secret."))

		verify_dns_provider = (
			self.has_value_changed("root_domain_name")
			or self.has_value_changed("dns_provider")
			or self.has_value_changed("dns_provider_access_key")
			or self.has_value_changed("dns_provider_access_secret")
			or self.has_value_changed("dns_provider_token")
			or self.has_value_changed("dns_provider_username")
			or self.has_value_changed("dns_provider_client_ip")
			or self.has_value_changed("dns_provider_key")
			or self.has_value_changed("dns_provider_secret")
		)

		if verify_dns_provider:
			dns_provider = get_dns_provider(self)
			dns_provider.read_dns_records("MX")

	def validate_signup_domains(self) -> None:
		"""Validates the Signup Domains."""

		if not self.signup_domains:
			return

		principals = frappe.db.get_all(
			"Principal Settings",
			{"name": ["in", [d.principal for d in self.signup_domains]]},
			["principal_name", "is_verified"],
		)

		if not principals:
			self.signup_domains = []
			return

		for principal in principals:
			if not principal.is_verified:
				frappe.throw(_("Domain {0} is not verified.").format(frappe.bold(principal.principal_name)))

	def validate_jmap_push_subscription_keys(self) -> None:
		"""Validates site-level JMAP push subscription encryption keys."""

		p256dh = (self.jmap_push_p256dh or "").strip()
		auth = (self.get_password("jmap_push_auth") if self.jmap_push_auth else "").strip()
		private_key = (
			self.get_password("jmap_push_private_key") if self.jmap_push_private_key else ""
		).strip()

		set_count = sum([bool(p256dh), bool(auth), bool(private_key)])
		if set_count not in (0, 3):
			frappe.throw(
				_(
					"JMAP Push Subscription keys are incomplete. Use Actions → Generate JMAP Push Keys to regenerate them."
				)
			)

		if set_count == 0:
			return

		for value, label in (
			(p256dh, _("P256DH")),
			(private_key, _("Private Key")),
			(auth, _("Auth")),
		):
			if not self._is_urlsafe_base64(value):
				frappe.throw(
					_("The JMAP Push Subscription {0} key must be URL-safe base64 encoded.").format(
						frappe.bold(label)
					)
				)

		try:
			from cryptography.hazmat.primitives.asymmetric import ec
			from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

			def _b64decode(s: str) -> bytes:
				return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

			priv_bytes = _b64decode(private_key)
			priv = ec.derive_private_key(int.from_bytes(priv_bytes, "big"), ec.SECP256R1())
			computed_pub = priv.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
			expected_pub = _b64decode(p256dh)
			if computed_pub != expected_pub:
				frappe.throw(
					_("The JMAP Push Subscription Private Key does not correspond to the P256DH public key.")
				)
		except frappe.exceptions.ValidationError:
			raise
		except Exception as e:
			frappe.throw(_("Invalid JMAP Push Subscription keys: {0}").format(str(e)))

	@frappe.whitelist()
	def generate_jmap_push_keys(self) -> None:
		"""Generates new JMAP push subscription encryption keys and saves them."""

		self._generate_jmap_push_keys()
		frappe.msgprint(_("JMAP Push keys generated successfully."), alert=True)

	def _generate_jmap_push_keys(self) -> None:
		"""Generates a new ECDH P-256 key pair and auth secret for JMAP push encryption and saves them."""

		from cryptography.hazmat.primitives.asymmetric import ec
		from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

		private_key = ec.generate_private_key(ec.SECP256R1())
		private_key_bytes = private_key.private_numbers().private_value.to_bytes(32, "big")
		public_key_bytes = private_key.public_key().public_bytes(
			Encoding.X962, PublicFormat.UncompressedPoint
		)
		auth_bytes = os.urandom(16)

		self.jmap_push_p256dh = base64.urlsafe_b64encode(public_key_bytes).decode()
		self.jmap_push_private_key = base64.urlsafe_b64encode(private_key_bytes).decode()
		self.jmap_push_auth = base64.urlsafe_b64encode(auth_bytes).decode()

		self.flags.ignore_mandatory = True
		self.flags.ignore_validate = True
		self.save()

	@staticmethod
	def _is_urlsafe_base64(value: str) -> bool:
		"""Returns True if the given value is URL-safe base64 encoded."""

		try:
			padding = "=" * (-len(value) % 4)
			base64.urlsafe_b64decode(f"{value}{padding}".encode())
			return True
		except Exception:
			return False

	def handle_root_domain_change(self) -> None:
		"""Resets DNS Record verification and notifies user after root domain change."""

		frappe.db.set_value("DNS Record", {"is_verified": 1}, "is_verified", 0)

		if self.has_value_changed("root_domain_name"):
			dns_record_list_link = f'<a href="/app/dns-record">{_("DNS Records")}</a>'
			frappe.msgprint(
				_("Please verify the {0} for the new {1}.").format(
					dns_record_list_link, frappe.bold("Root Domain Name")
				)
			)

	def clear_cache(self) -> None:
		"""Clears the Cache."""

		frappe.cache.delete_value("mail-settings")
