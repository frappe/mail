# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document


class DKIMKey(Document):
	def autoname(self) -> None:
		self.name = self.domain_name

	def validate(self) -> None:
		self.validate_domain_name()
		self.validate_key_size()

		if (
			self.is_new()
			or self.has_value_changed("key_size")
			or not self.private_key
			or not self.public_key
		):
			self.generate_dkim_keys()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete DKIM Key."))

	def validate_domain_name(self) -> None:
		"""Validates the Domain Name."""

		if not self.domain_name:
			frappe.throw(_("Domain Name is mandatory"))

	def validate_key_size(self) -> None:
		"""Validates the Key Size."""

		if self.key_size:
			if cint(self.key_size) < 1024:
				frappe.throw(_("Key Size must be greater than 1024."))
		else:
			self.key_size = frappe.db.get_single_value(
				"Mail Settings", "default_dkim_key_size", cache=True
			)

	def generate_dkim_keys(self) -> None:
		"""Generates the DKIM Keys."""

		self.private_key, self.public_key = generate_dkim_keys(cint(self.key_size))


def create_or_update_dkim_key(
	domain_name: str, key_size: int | None = None
) -> "DKIMKey":
	"""Creates a DKIM Key document if it does not exist, else updates it."""

	doc = None

	if frappe.db.exists("DKIM Key", domain_name):
		doc = frappe.get_doc("DKIM Key", domain_name)
	else:
		doc = frappe.new_doc("DKIM Key")
		doc.domain_name = domain_name

	doc.key_size = key_size
	doc.flags.ignore_links = True
	doc.save(ignore_permissions=True)

	return doc


def generate_dkim_keys(key_size: int = 1024) -> tuple[str, str]:
	"""Generates the DKIM Keys."""

	def get_filtered_dkim_key(key_pem: str) -> str:
		"""Returns the filtered DKIM Key."""

		key_pem = "".join(key_pem.split())
		key_pem = (
			key_pem.replace("-----BEGINPUBLICKEY-----", "")
			.replace("-----ENDPUBLICKEY-----", "")
			.replace("-----BEGINRSAPRIVATEKEY-----", "")
			.replace("----ENDRSAPRIVATEKEY-----", "")
		)

		return key_pem

	from cryptography.hazmat.backends import default_backend
	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric import rsa

	private_key = rsa.generate_private_key(
		public_exponent=65537, key_size=key_size, backend=default_backend()
	)
	public_key = private_key.public_key()

	private_key_pem = private_key.private_bytes(
		encoding=serialization.Encoding.PEM,
		format=serialization.PrivateFormat.TraditionalOpenSSL,
		encryption_algorithm=serialization.NoEncryption(),
	).decode()
	public_key_pem = public_key.public_bytes(
		encoding=serialization.Encoding.PEM,
		format=serialization.PublicFormat.SubjectPublicKeyInfo,
	).decode()

	private_key = private_key_pem
	public_key = get_filtered_dkim_key(public_key_pem)

	return private_key, public_key
