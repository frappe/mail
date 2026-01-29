# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from typing import Literal

import frappe
from frappe import _, unscrub
from frappe.model.document import Document
from frappe.utils import cint, today, validate_email_address

from mail.backend import MailBackendAPI, get_mail_backend_api
from mail.client.doctype.identity.identity import _add_identity as add_identity
from mail.jmap import invalidate_jmap_cache
from mail.server.doctype.mail_principal_binding.mail_principal_binding import (
	create_principal_binding,
	delete_principal_binding,
	get_tenant_principals,
	update_principal_binding,
)
from mail.utils import (
	generate_app_password,
	generate_dkim_keys,
	get_dkim_selector,
	get_spf_host_for_cluster,
	hash_password,
	is_catch_all_address,
	is_probable_hash,
	parse_filters,
	parse_token,
	snake_to_camel,
)
from mail.utils.cache import get_cluster_for_tenant, get_root_domain_name
from mail.utils.dns import verify_dns_record
from mail.utils.user import get_principal_tenant, get_tenant_for_user, is_system_manager, is_tenant_admin
from mail.utils.validation import (
	ensure_access_to_tenant,
	ensure_emails_belong_to_tenant_domains,
	ensure_groups_belong_to_tenant,
	ensure_lists_belong_to_tenant,
	ensure_members_belong_to_tenant,
	ensure_principal_belong_to_tenant,
	ensure_tenant_has_cluster,
	is_subaddressed_email,
	validate_max_accounts,
	validate_max_domains,
	validate_max_groups,
	validate_max_lists,
	validate_wildcard_email,
)

SETTINGS_ENDPOINT = "/api/settings"
PRINCIPAL_ENDPOINT = "/api/principal"
DNS_RECORDS_ENDPOINT = "/api/dns/records"

TYPE_MAP = {
	"apiKey": "API Key",
	"domain": "Domain",
	"group": "Group",
	"individual": "Individual",
	"list": "List",
	"oauthClient": "OAuth Client",
	"role": "Role",
}


class MailPrincipal(Document):
	@property
	def _app_passwords(self) -> list[str]:
		"""Returns a list of app password identifiers."""

		return [ap.identifier for ap in self.get("app_passwords") or []]

	@property
	def _emails(self) -> list[str]:
		"""Returns a list of email addresses associated with the principal."""

		return [e.value for e in self.get("emails") or []]

	@property
	def _member_of(self) -> list[str]:
		"""Returns a list of groups the principal is a member of."""

		return [m.value for m in self.get("member_of") or []]

	@property
	def _roles(self) -> list[str]:
		"""Returns a list of roles assigned to the principal."""

		return [r.value for r in self.get("roles") or []]

	@property
	def _lists(self) -> list[str]:
		"""Returns a list of lists the principal is part of."""

		return [l.value for l in self.get("lists") or []]

	@property
	def _members(self) -> list[str]:
		"""Returns a list of members of the principal."""

		return [m.value for m in self.get("members") or []]

	@property
	def _enabled_permissions(self) -> list[str]:
		"""Returns a list of enabled permissions."""

		return [p.type for p in self.get("permissions") or [] if p.value == "On"]

	@property
	def _disabled_permissions(self) -> list[str]:
		"""Returns a list of disabled permissions."""

		return [p.type for p in self.get("permissions") or [] if p.value == "Off"]

	@property
	def _external_members(self) -> list[str]:
		"""Returns a list of external members of the principal."""

		return [em.value for em in self.get("external_members") or []]

	@property
	def is_verified(self) -> bool | None:
		if self.type != "Domain":
			return None

		return bool(
			frappe.db.get_value("Mail Principal Binding", {"principal_name": self.name}, "is_verified")
		)

	def db_insert(self, *args, **kwargs) -> None:
		self._create()

	def load_from_db(self) -> "MailPrincipal":
		principal = self._get()
		return super(Document, self).__init__(principal)

	def db_update(self) -> None:
		self._update()
		self.reload()

	def delete(self) -> None:
		self._delete()

	@staticmethod
	def get_list(filters=None, page_length=20, **kwargs) -> list:
		filters = parse_filters(filters)
		tenant = filters.get("tenant") or get_tenant_for_user(frappe.session.user)
		type = filters.get("type")
		text = filters.get("text")

		if not tenant:
			if is_system_manager(frappe.session.user):
				frappe.msgprint(_("Please specify tenant to fetch principals."), alert=True)
				return []
			frappe.throw(_("You do not have permission to access principals."))

		limit = cint(kwargs.get("start", 1)) + page_length
		principals, total = MailPrincipal._get_all(tenant, type, limit=limit)

		frappe.cache.set_value(_get_total_cache_key(tenant, type, text), total, expires_in_sec=600)

		return principals

	@staticmethod
	def get_count(filters=None, **kwargs) -> int:
		filters = parse_filters(filters)
		tenant = filters.get("tenant") or get_tenant_for_user(frappe.session.user)
		type = filters.get("type")
		text = filters.get("text")

		if not tenant:
			return 0

		ensure_access_to_tenant(tenant)

		return cint(frappe.cache.get_value(_get_total_cache_key(tenant, type, text)))

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	def before_insert(self) -> None:
		if not self.tenant:
			frappe.throw(_("Tenant is required."))

		if self.type == "Domain":
			validate_max_domains(self.tenant)
		elif self.type == "Group":
			validate_max_groups(self.tenant)
		elif self.type == "Individual":
			validate_max_accounts(self.tenant)
		elif self.type == "List":
			validate_max_lists(self.tenant)

	def validate(self) -> None:
		if self.type in ["API Key", "Group", "OAuth Client", "Role"]:
			raise NotImplementedError(_("Principal type {0} is not supported yet.").format(self.type))

		if not bool(self.flags.ignore_permissions):
			ensure_access_to_tenant(self.tenant)

		ensure_tenant_has_cluster(self.tenant)

		if self.type == "Domain":
			if "." not in self._name:
				frappe.throw(_("Invalid domain name provided for principal."))

		if self.type in ["Group", "Individual", "List"]:
			if is_catch_all_address(self._name):
				frappe.throw(_("Catch-all email addresses are not allowed for principals."))

			emails = [self._name, *self._emails]
			for email in emails:
				if not is_catch_all_address(email):
					validate_email_address(email, True)
				validate_wildcard_email(email)
				is_subaddressed_email(email, raise_exception=True)

			ensure_emails_belong_to_tenant_domains(self.tenant, emails)

		if self.type in ["Group", "Individual"]:
			for group in self._member_of:
				validate_email_address(group, True)
				validate_wildcard_email(group)

			ensure_groups_belong_to_tenant(self.tenant, self._member_of)

			for lst in self._lists:
				validate_email_address(lst, True)
				validate_wildcard_email(lst)

			ensure_lists_belong_to_tenant(self.tenant, self._lists)

		if self.type in ["Group", "List"]:
			for member in self._members:
				validate_email_address(member, True)
				validate_wildcard_email(member)

			ensure_members_belong_to_tenant(self.tenant, self._members)

		if self.type == "List":
			for member in self._external_members:
				validate_email_address(member, True)

	@frappe.whitelist()
	def verify_dns_records(self) -> bool:
		"""Verifies the DNS Records."""

		if self.type != "Domain":
			frappe.throw(_("DNS Records can only be verified for Domain principals."))

		errors = []
		warnings = []
		is_verified = False

		for record in self.dns_records:
			if not verify_dns_record(record.host, record.type, record.value):
				message = _("Row #{0}: Failed to verify {1} : {2}").format(
					record.idx, frappe.bold(record.type), frappe.bold(record.host)
				)
				if record.mandatory:
					errors.append(message)
				else:
					warnings.append(message)

		if not errors:
			is_verified = True
			frappe.msgprint(_("DNS Records verified successfully."), indicator="green", alert=True)
		else:
			frappe.msgprint(errors, title="DNS Verification Failed", indicator="red", as_list=True)

		update_principal_binding(self.name, is_verified=cint(is_verified))

		return is_verified

	@frappe.whitelist()
	def refresh_dns_records(self) -> None:
		"""Refreshes the DNS Records."""

		ensure_access_to_tenant(self.tenant)

		if self.type != "Domain":
			frappe.throw(_("DNS Records can only be refreshed for Domain principals."))

		_remove_principal_from_cache(self.tenant, self.name)
		self.reload()

		frappe.msgprint(_("DNS Records refreshed successfully."), indicator="green", alert=True)

	@frappe.whitelist()
	def rotate_dkim_keys(self) -> None:
		"""Rotates the DKIM Keys."""

		ensure_access_to_tenant(self.tenant)

		if self.type != "Domain":
			frappe.throw(_("DKIM Keys can only be rotated for Domain principals."))

		backend = get_mail_backend_api("Mail Cluster", get_cluster_for_tenant(self.tenant))

		self._delete_dkim_signature(backend, "rsa-sha256", raise_exception=False)
		self._create_dkim_signature(backend, "rsa-sha256", raise_exception=False)

		if bool(frappe.conf.enable_ed25519_dkim):
			self._delete_dkim_signature(backend, "ed25519-sha256", raise_exception=False)
			self._create_dkim_signature(backend, "ed25519-sha256", raise_exception=False)

		update_principal_binding(self.name, is_verified=0)

		_remove_principal_from_cache(self.tenant, self.name)
		self.reload()

		frappe.msgprint(_("DKIM Keys rotated successfully."), indicator="green", alert=True)

	@frappe.whitelist()
	def sync_jmap_identities(self) -> None:
		"""Syncs JMAP identities for the principal."""

		ensure_access_to_tenant(self.tenant)
		self._sync_jmap_identities()

	def _create(self) -> None:
		"""Creates the principal in the backend."""

		self.name = self._name
		_secrets = []
		_emails = []
		_member_of = []
		_roles = []
		_lists = []
		_members = []
		_enabled_permissions = []
		_disabled_permissions = []
		_external_members = []
		principals_to_invalidate = set()

		if self.type == "Individual":
			_roles = ["user"]
			_secrets.append(hash_password(self.password))
			if self.app_passwords:
				for ap in self.app_passwords:
					_secrets.append(generate_app_password(ap.identifier, ap.password))

		if self.type in ["Group", "Individual", "List"]:
			_emails = [self.name, *self._emails]
			principals_to_invalidate.update([email.split("@")[1] for email in _emails])

		if self.type in ["Group", "Individual"]:
			if _member_of := self._member_of:
				principals_to_invalidate.update(_member_of)
			if _lists := self._lists:
				principals_to_invalidate.update(_lists)
			_disabled_permissions = self._disabled_permissions

		if self.type in ["Group", "List"]:
			if _members := self._members:
				principals_to_invalidate.update(_members)

		if self.type == "List":
			_external_members = self._external_members

		payload = {
			"name": self.name,
			"type": _get_principal_type(self.type),
			"quota": cint(self.quota) or cint(frappe.conf.default_mail_quota) or 1024**3,
			"description": self.description or "",
			"secrets": _secrets,
			"emails": _emails,
			"memberOf": _member_of,
			"roles": _roles,
			"lists": _lists,
			"members": _members,
			"enabledPermissions": _enabled_permissions,
			"disabledPermissions": _disabled_permissions,
			"externalMembers": _external_members,
			"locale": self.locale,
		}
		backend = get_mail_backend_api("Mail Cluster", get_cluster_for_tenant(self.tenant))
		response = backend.request("POST", PRINCIPAL_ENDPOINT, data=json.dumps(payload))

		if response.json().get("error"):
			frappe.throw(_("Failed to add principal {0}: {1}").format(frappe.bold(self.name), response.text))

		create_principal_binding(self.tenant, self.name, self.type)

		if self.type == "Domain":
			try:
				self._create_dkim_signature(backend, "rsa-sha256", raise_exception=False)

				if bool(frappe.conf.enable_ed25519_dkim):
					self._create_dkim_signature(backend, "ed25519-sha256", raise_exception=False)
			except Exception:
				frappe.log_error(
					title=f"Failed to create DKIM signature for domain {self.name}",
					message=frappe.get_traceback(with_context=True),
				)

		for pname in principals_to_invalidate:
			_remove_principal_from_cache(self.tenant, pname)

	def _create_dkim_signature(
		self,
		backend: MailBackendAPI,
		algorithm: Literal["rsa-sha256", "ed25519-sha256"],
		raise_exception: bool = True,
	) -> None:
		"""Creates DKIM signature for the domain principal."""

		if self.type != "Domain":
			frappe.throw(_("DKIM signature can only be created for Domain principals."))

		key_type = algorithm.split("-")[0]
		selector = get_dkim_selector(key_type)
		rsa_key_size = cint(frappe.conf.rsa_key_size) or 2048
		private_key, _public_key = generate_dkim_keys(algorithm, rsa_key_size)

		payload = [
			{
				"type": "insert",
				"prefix": f"signature.{key_type}-{self.name}",
				"values": [
					["report", "true"],
					["selector", selector],
					["canonicalization", "relaxed/relaxed"],
					["private-key", private_key],
					["algorithm", algorithm],
					["domain", self.name],
				],
				"assert_empty": True,
			}
		]
		response = backend.request("POST", SETTINGS_ENDPOINT, data=json.dumps(payload))

		if response.json().get("error"):
			message = _("Failed to create DKIM signature for domain {0}").format(frappe.bold(self.name))
			frappe.log_error(title=message, message=frappe.get_traceback(with_context=True))

			if raise_exception:
				frappe.throw(message)
			else:
				frappe.msgprint(message, alert=True)

	def _sync_jmap_identities(self) -> None:
		"""Syncs JMAP identities for the principal."""

		if self.type != "Individual":
			frappe.throw(_("JMAP Identities can only be synced for Individual principals."))

		ensure_access_to_tenant(self.tenant)
		ensure_tenant_has_cluster(self.tenant)

		if not frappe.db.exists(
			"Mail Principal Binding",
			{"tenant": self.tenant, "principal_name": self.name, "principal_type": "Individual"},
		):
			return

		identities = frappe.db.get_all("Identity", {"user": self.name})
		identities_emails_map = {identity["email"]: identity["name"] for identity in identities}
		identities_emails = set(identities_emails_map.keys())

		principal = frappe.get_doc("Mail Principal", self.name)
		principal_emails = set([principal.name, *principal._emails])
		explicit_emails = {email for email in principal_emails if not is_catch_all_address(email)}

		identities_to_remove = identities_emails - explicit_emails
		identities_to_add = explicit_emails - identities_emails

		for email in identities_to_remove:
			frappe.delete_doc("Identity", identities_emails_map[email])

		for email in identities_to_add:
			add_identity(self.name, email, principal.description)

		invalidate_jmap_cache(self.name)

	@staticmethod
	def _fetch(
		backend: MailBackendAPI, pname: str, skip_dns_records: bool = False, ignore_not_found: bool = True
	) -> dict:
		"""Fetches the principal from the backend."""

		response = backend.request("GET", f"{PRINCIPAL_ENDPOINT}/{pname}")
		if response.json().get("error") == "notFound":
			if not ignore_not_found:
				frappe.throw(_("Principal {0} not found in backend.").format(frappe.bold(pname)))

			return {}

		principal = response.json()["data"]

		dns_records = []
		if principal["type"] == "domain" and not skip_dns_records:
			response = backend.request("GET", f"{DNS_RECORDS_ENDPOINT}/{pname}")
			if response.json().get("error") == "notFound":
				if not ignore_not_found:
					frappe.throw(
						_("DNS Records for principal {0} not found in backend.").format(frappe.bold(pname))
					)
			else:
				dns_records = response.json()["data"]

		principal["dnsRecords"] = dns_records

		return principal

	def _get(self, skip_dns_records: bool = False, ignore_cache: bool = False) -> dict:
		"""Returns the principal details."""

		tenant = get_principal_tenant(self.name)
		ensure_access_to_tenant(tenant)
		ensure_tenant_has_cluster(tenant)
		ensure_principal_belong_to_tenant(tenant, self.name)

		if not ignore_cache:
			if cached := _get_principal_from_cache(tenant, self.name):
				return cached

		backend = get_mail_backend_api("Mail Cluster", get_cluster_for_tenant(tenant))
		principal = MailPrincipal._fetch(
			backend, self.name, skip_dns_records=skip_dns_records, ignore_not_found=False
		)
		formatted = MailPrincipal._format(tenant, principal)
		_store_principal_in_cache(tenant, self.name, formatted)

		return formatted

	@staticmethod
	def _get_all(
		tenant: str,
		type: str | None = None,
		filter: str | None = None,
		page: int = 1,
		limit: int = 10,
	) -> tuple[list, int]:
		"""Returns all principals for the tenant."""

		ensure_access_to_tenant(tenant)

		tenant_principals, total = get_tenant_principals(tenant, type, filter, page, limit)

		if total == 0:
			return [], total

		cluster = get_cluster_for_tenant(tenant)
		if not cluster:
			frappe.msgprint(
				_("Tenant {0} is not assigned to any cluster.").format(frappe.bold(tenant)), alert=True
			)
			return [], 0

		backend = get_mail_backend_api("Mail Cluster", cluster)

		principals = []
		for pname in tenant_principals:
			if principal := _get_principal_from_cache(tenant, pname):
				principals.append(principal)
				continue

			principal = MailPrincipal._fetch(backend, pname, ignore_not_found=True)

			if not principal:
				total -= 1
				continue

			formatted = MailPrincipal._format(tenant, principal)
			_store_principal_in_cache(tenant, pname, formatted)
			principals.append(formatted)

		return principals, total

	def _update(self) -> None:
		"""Updates the principal in the backend."""

		ensure_principal_belong_to_tenant(self.tenant, self.name)
		backend = get_mail_backend_api("Mail Cluster", get_cluster_for_tenant(self.tenant))
		existing_principal = frappe._dict(
			MailPrincipal._fetch(backend, self.name, skip_dns_records=True, ignore_not_found=False)
		)

		if self.name != self._name or self.type != TYPE_MAP[existing_principal.type]:
			frappe.throw(
				_("Principal name or type cannot be changed directly. Please create a new principal.")
			)

		updates = {
			"name": self._name,
			"description": self.description or "",
			"secrets": [],
			"emails": [],
			"member_of": [],
			"roles": [],
			"lists": [],
			"members": [],
			"enabled_permissions": [],
			"disabled_permissions": [],
			"external_members": [],
		}

		if self.type == "Individual":
			updates["locale"] = self.locale or ""
			updates["roles"] = self._roles
			if self.password:
				password = self.password
				hashed_password = password if is_probable_hash(password) else hash_password(password)
				updates["secrets"].append(hashed_password)
			else:
				for password in existing_principal.secrets or []:
					if not password.startswith("$app$"):
						updates["secrets"].append(password)

			if self.app_passwords:
				for ap in self.app_passwords:
					updates["secrets"].append(ap.value or generate_app_password(ap.identifier, ap.password))

		if self.type in ["Group", "Individual", "List"]:
			updates["emails"] = [self._name, *self._emails]

		if self.type in ["Group", "Individual"]:
			updates["quota"] = cint(self.quota)
			updates["member_of"] = self._member_of
			updates["lists"] = self._lists
			updates["disabled_permissions"] = self._disabled_permissions

		if self.type in ["Group", "List"]:
			updates["members"] = self._members

		if self.type == "List":
			updates["external_members"] = self._external_members

		actions = []
		principals_to_invalidate = set()
		for field, value in updates.items():
			if field in ["name", "quota", "description", "locale"]:
				if existing_principal.get(field) != value:
					actions.append({"action": "set", "field": field, "value": value})
				continue

			server_field = snake_to_camel(field)
			existing_values = existing_principal.get(server_field)
			if not isinstance(existing_values, list):
				existing_values = []

			if values_to_add := set(value) - set(existing_values):
				for v in values_to_add:
					actions.append({"action": "addItem", "field": server_field, "value": v})

				if field == "emails" and self.type in ["Group", "Individual", "List"]:
					principals_to_invalidate.update([email.split("@")[1] for email in values_to_add])

				if (field in ["member_of", "lists"] and self.type in ["Group", "Individual"]) or (
					field == "members" and self.type in ["Group", "List"]
				):
					principals_to_invalidate.update(values_to_add)

			if values_to_remove := set(existing_values) - set(value):
				for v in values_to_remove:
					actions.append({"action": "removeItem", "field": server_field, "value": v})

				if field == "emails" and self.type in ["Group", "Individual", "List"]:
					principals_to_invalidate.update([email.split("@")[1] for email in values_to_remove])

				if (field in ["member_of", "lists"] and self.type in ["Group", "Individual"]) or (
					field == "members" and self.type in ["Group", "List"]
				):
					principals_to_invalidate.update(values_to_remove)

		response = backend.request("PATCH", f"{PRINCIPAL_ENDPOINT}/{self.name}", data=json.dumps(actions))

		if response.json().get("error"):
			frappe.throw(
				_("Failed to update principal {0}: {1}").format(frappe.bold(self.name), response.text)
			)

		_remove_principal_from_cache(self.tenant, self.name)

		if self.name != self._name or self.type != TYPE_MAP[existing_principal.type]:
			update_principal_binding(self.name, principal_name=self._name, principal_type=self.type)

		for pname in principals_to_invalidate:
			_remove_principal_from_cache(self.tenant, pname)

		if self.type == "Individual":
			try:
				self._sync_jmap_identities()
			except Exception:
				frappe.log_error(
					title=f"Failed to sync JMAP identities for principal {self.name}",
					message=frappe.get_traceback(with_context=True),
				)

		self.name = self._name
		self.password = None

	def _delete(self) -> None:
		"""Deletes the principal from the backend."""

		_remove_principal_from_cache(self.tenant, self.name)
		principal = frappe.get_doc("Mail Principal", self.name)

		if principal.type == "Domain":
			if principal.total_members > 0:
				frappe.throw(
					_("Cannot delete domain {0} as there are addresses associated with it.").format(
						frappe.bold(self.name)
					)
				)

		backend = get_mail_backend_api("Mail Cluster", get_cluster_for_tenant(self.tenant))
		backend.request("DELETE", f"{PRINCIPAL_ENDPOINT}/{self.name}")
		delete_principal_binding(self.name, raise_exception=False)

		# If the principal is an Individual, remove member from tenant and delete User
		if principal.type == "Individual":
			invalidate_jmap_cache(self.name)

			if member := frappe.db.exists("Mail Tenant Member", {"tenant": self.tenant, "user": self.name}):
				frappe.delete_doc("Mail Tenant Member", member, ignore_permissions=True)

			if frappe.db.exists("User", self.name):
				frappe.delete_doc("User", self.name, ignore_permissions=True)

		elif principal.type == "Domain":
			self._delete_dkim_signature(backend, "rsa-sha256", raise_exception=False)
			if bool(frappe.conf.enable_ed25519_dkim):
				self._delete_dkim_signature(backend, "ed25519-sha256", raise_exception=False)

		principals_to_invalidate = set()
		if principal.type in ["Group", "Individual", "List"]:
			principals_to_invalidate.update([email.split("@")[1] for email in principal._emails])
		if principal.type in ["Group", "Individual"]:
			principals_to_invalidate.update(principal._member_of)
			principals_to_invalidate.update(principal._lists)
		if principal.type in ["Group", "List"]:
			principals_to_invalidate.update(principal._members)

		for pname in principals_to_invalidate:
			_remove_principal_from_cache(self.tenant, pname)

	def _delete_dkim_signature(
		self,
		backend: MailBackendAPI,
		algorithm: Literal["rsa-sha256", "ed25519-sha256"],
		raise_exception: bool = True,
	) -> None:
		"""Deletes DKIM signature for the domain principal."""

		if self.type != "Domain":
			frappe.throw(_("DKIM signature can only be deleted for Domain principals."))

		key_type = algorithm.split("-")[0]
		payload = [
			{
				"type": "clear",
				"prefix": f"signature.{key_type}-{self.name}",
			}
		]
		response = backend.request("POST", SETTINGS_ENDPOINT, data=json.dumps(payload))
		if response.json().get("error"):
			message = _("Failed to delete DKIM signature for domain {0}").format(frappe.bold(self.name))
			frappe.log_error(title=message, message=frappe.get_traceback(with_context=True))

			if raise_exception:
				frappe.throw(message)
			else:
				frappe.msgprint(message, alert=True)

	@staticmethod
	def _format(tenant: str, principal: dict) -> dict:
		"""Formats the principal data from backend to Frappe Doc format."""

		type = _get_local_type(principal["type"])
		formatted = {
			"type": type,
			"tenant": tenant,
			"id": principal["id"],
			"name": principal["name"],
			"_name": principal["name"],
			"description": principal.get("description"),
			"members": 0,
			"creation": today(),
			"modified": today(),
		}

		if type == "Domain":
			cluster = get_cluster_for_tenant(tenant)
			formatted.update(
				{
					"dns_records": MailPrincipal._format_dns_records(
						principal["name"], cluster, principal["dnsRecords"]
					),
					"total_members": cint(principal.get("members")),
				}
			)

		if type in ["API Key", "Group", "Individual"]:
			permissions = [
				{"description": unscrub(p), "type": p, "value": "On"}
				for p in principal.get("enabledPermissions", [])
			] + [
				{"description": unscrub(p), "type": p, "value": "Off"}
				for p in principal.get("disabledPermissions", [])
			]
			formatted.update(
				{
					"roles": [{"value": r} for r in principal.get("roles", [])],
					"enabled_permissions": json.dumps(principal.get("enabledPermissions", []), indent=4),
					"disabled_permissions": json.dumps(principal.get("disabledPermissions", []), indent=4),
					"permissions": permissions,
				}
			)

		if type in ["API Key", "Individual"]:
			formatted["secrets"] = json.dumps(principal.get("secrets", []), indent=4)

		if type in ["Group", "Individual"]:
			quota = str(principal.get("quota") or 0)
			used_quota = str(principal.get("usedQuota") or 0)
			formatted.update(
				{
					"quota": quota,
					"used_quota": used_quota,
					"used_percentage": (cint(cint(used_quota) / cint(quota) * 100) if cint(quota) > 0 else 0),
					"member_of": [{"value": m} for m in principal.get("memberOf", [])],
					"lists": [{"value": l} for l in principal.get("lists", [])],
				}
			)

		if type in ["Group", "Individual", "List"]:
			formatted["emails"] = [{"value": e} for e in principal.get("emails", [])]

		if type in ["Group", "List"]:
			members = [{"value": m} for m in principal.get("members", [])]
			formatted.update(
				{
					"members": members,
					"total_members": len(members),
				}
			)

		if type == "Individual":
			app_passwords = [
				{"identifier": parse_token(s)["decoded_metadata"], "value": s}
				for s in principal.get("secrets", [])
				if s.startswith("$app$")
			]
			formatted.update(
				{
					"locale": principal.get("locale"),
					"app_passwords": app_passwords,
				}
			)

		if type == "List":
			formatted["external_members"] = [{"value": m} for m in principal.get("externalMembers", [])]

		return formatted

	@staticmethod
	def _format_dns_records(domain: str, cluster: str, dns_records: list[dict]) -> list[dict]:
		"""Formats the DNS records for the domain principal."""

		def replace_mx_records() -> None:
			"""Replace existing MX records with mail server MX records."""

			nonlocal dns_records
			dns_records = [record for record in dns_records if record["type"] != "MX"]

			servers = frappe.db.get_all(
				"Mail Server",
				{"cluster": cluster, "enabled": 1, "outbound_only": 0, "include_in_mx_records": 1},
				["hostname", "priority"],
				order_by="priority asc",
			)
			for server in servers:
				dns_records.append(
					{
						"type": "MX",
						"name": domain,
						"content": f"{server['priority']} {server['hostname'].split(':')[0]}.",
					}
				)

		def replace_spf_record() -> None:
			"""Replace existing SPF record with mail server SPF record."""

			nonlocal dns_records
			dns_records = [
				record
				for record in dns_records
				if not (record["type"] == "TXT" and "v=spf1" in record["content"])
			]

			spf_host = get_spf_host_for_cluster(cluster)
			dns_records.append(
				{
					"type": "TXT",
					"name": domain,
					"content": f"v=spf1 include:{spf_host}.{get_root_domain_name()} ~all",
				}
			)

		def is_internal_hostname(host: str) -> bool:
			"""Return True if the hostname does NOT end with domain."""

			host = host.rstrip(".")
			return not host.endswith(domain)

		def rewrite_last_hostname(content: str) -> str:
			"""Rewrite only the last token in DNS content (SRV, CNAME)."""

			parts = content.split()
			if not parts:
				return content

			last = parts[-1].rstrip(".")

			if is_internal_hostname(last):
				parts[-1] = hostname

			return " ".join(parts)

		def infer_category(record: dict) -> str:
			"""Infers the category of the DNS record based on its type and name."""

			t = record["type"]
			name = record["name"]

			if t == "MX":
				return "Receiving"

			if t == "TXT":
				content = record.get("content", "")
				if name.startswith("_dmarc"):
					return "DMARC"
				if "spf1" in content:
					return "Sending"
				if "domainkey" in name:
					return "DKIM"
				if name.startswith("_smtp._tls"):
					return "TLS Reporting"
				return "TXT"

			if t == "CNAME":
				if "autoconfig" in name:
					return "Auto-config"
				if "autodiscover" in name:
					return "Auto-discover"
				return "Alias"

			if t == "SRV":
				if "_imap" in name or "_pop3" in name:
					return "Receiving"
				if "_submission" in name or "_submissions" in name:
					return "Sending"
				return "Server"

			return "Other"

		def parse_priority(record: dict) -> str:
			"""Parses the priority from the DNS record content if applicable."""

			if record["type"] in ["MX", "SRV"]:
				parts = record["content"].split()
				return str(parts[0])
			return "-"

		def is_mandatory(record: dict) -> bool:
			"""Define which DNS records are required for proper email authentication."""

			category = infer_category(record)
			content = record["content"]

			if category == "Sending" and "spf1" in content:
				return True
			if category == "DMARC":
				return True
			if category == "DKIM":
				return True
			if record["type"] == "MX":
				return False

			return False

		domain = domain.rstrip(".")
		hostname = cluster.rstrip(".") + "."

		replace_mx_records()
		replace_spf_record()

		formatted_records = []
		for record in dns_records:
			rewritten_content = record["content"]
			if record["type"] in ("CNAME", "SRV"):
				rewritten_content = rewrite_last_hostname(rewritten_content)

			entry = {
				"category": infer_category(record),
				"type": record["type"],
				"host": record["name"],
				"priority": parse_priority(record),
				"value": rewritten_content,
				"mandatory": cint(is_mandatory(record)),
				"ttl": cint(frappe.conf.default_dns_ttl) or 3600,
			}

			formatted_records.append(entry)

		return sorted(
			formatted_records, key=lambda x: (not x["mandatory"], x["category"], x["type"], x["host"])
		)


def _get_local_type(principal_type: str) -> str:
	"""Returns the local principal type for the given backend principal type."""

	return TYPE_MAP[principal_type]


def _get_principal_type(local_type: str) -> str:
	"""Returns the backend principal type for the given local principal type."""

	reversed_map = {v: k for k, v in TYPE_MAP.items()}
	return reversed_map[local_type]


def _get_total_cache_key(tenant: str, type: str | None, text: str | None) -> str:
	"""Returns a cache key for storing total count of principals for the given tenant, type and text."""

	return f"principals:{tenant}:{type}:{text}:total"


def _get_principal_cache_key(tenant: str, pname: str) -> str:
	"""Returns a cache key for the principal with the given tenant and principal name."""

	return f"principal:{tenant}:{pname}"


def _get_principal_from_cache(tenant: str, pname: str) -> dict | None:
	"""Returns the principal from cache if exists."""

	cache_key = _get_principal_cache_key(tenant, pname)
	return frappe.cache.get_value(cache_key)


def _store_principal_in_cache(tenant: str, pname: str, principal: dict) -> None:
	"""Store a principal in cache with TTL and maintain per-tenant bucket size."""

	cache_key = _get_principal_cache_key(tenant, pname)
	list_key = f"principal:{tenant}:names"
	principal_bucket_size = cint(frappe.conf.principal_bucket_size) or 100000

	principal_cache_ttl = cint(frappe.conf.principal_cache_ttl) or 2 * 24 * 60 * 60  # 2 days
	frappe.cache.set_value(cache_key, principal, expires_in_sec=principal_cache_ttl)
	frappe.cache.lpush(list_key, pname)

	frappe.cache.ltrim(list_key, 0, principal_bucket_size - 1)

	while frappe.cache.llen(list_key) > principal_bucket_size:
		if oldest_id := frappe.cache.rpop(list_key):
			frappe.cache.delete_key(_get_principal_cache_key(tenant, oldest_id))


def _remove_principal_from_cache(tenant: str, pname: str) -> None:
	"""Removes a principal from cache."""

	cache_key = _get_principal_cache_key(tenant, pname)
	frappe.cache.delete_value(cache_key)

	list_key = f"principal:{tenant}:names"
	frappe.cache.lrem(list_key, 0, pname)

	if not frappe.cache.llen(list_key):
		frappe.cache.delete_value(list_key)


def has_permission(doc: "Document", ptype: str, user: str | None = None) -> bool:
	if doc.doctype != "Mail Principal":
		return False

	user = user or frappe.session.user
	if is_system_manager(user):
		return True
	elif doc.tenant and is_tenant_admin(doc.tenant, user):
		if ptype == "create":
			return doc.type in ["List"]

		return ensure_principal_belong_to_tenant(doc.tenant, doc.name, raise_exception=False)

	return False
