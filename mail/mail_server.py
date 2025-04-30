import json
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urljoin

import frappe
import requests
from frappe import _

from mail.mail.doctype.mail_server_request.mail_server_request import (
	create_mail_server_request as create_request,
)
from mail.utils import get_dkim_selector

if TYPE_CHECKING:
	from mail.mail.doctype.mail_server_request.mail_server_request import MailServerRequest


@dataclass
class Principal:
	"""Dataclass to represent a principal."""

	name: str
	type: Literal["domain", "apiKey", "individual", "group"]
	id: int = 0
	quota: int = 0
	description: str = ""
	secrets: list[str] = field(default_factory=list)
	emails: list[str] = field(default_factory=list)
	urls: list[str] = field(default_factory=list)
	memberOf: list[str] = field(default_factory=list)
	roles: list[str] = field(default_factory=list)
	lists: list[str] = field(default_factory=list)
	members: list[str] = field(default_factory=list)
	enabledPermissions: list[str] = field(default_factory=list)
	disabledPermissions: list[str] = field(default_factory=list)
	externalMembers: list[str] = field(default_factory=list)


class MailServerAPI:
	"""Class to interact with the Mail Server API."""

	def __init__(
		self,
		base_url: str,
		api_key: str | None = None,
		username: str | None = None,
		password: str | None = None,
	) -> None:
		self.base_url = base_url

		self.__auth = None
		self.__headers = {}
		self.__session = requests.Session()

		if api_key:
			self.__headers.update({"Authorization": f"Bearer {api_key}"})
		elif username and password:
			self.__auth = (username, password)
		else:
			frappe.throw(_("API Key or Username and Password is required."))

	def request(
		self,
		method: str,
		endpoint: str,
		params: dict | None = None,
		data: dict | None = None,
		json: dict | None = None,
		files: dict | None = None,
		headers: dict[str, str] | None = None,
		timeout: int | tuple[int, int] = (60, 120),
	) -> Any:
		"""Makes an HTTP request to the Mail Server API."""

		url = urljoin(self.base_url, endpoint)
		headers = {**self.__headers, **(headers or {})}

		if files:
			headers.pop("content-type", None)

		return self.__session.request(
			method=method,
			url=url,
			params=params,
			data=data,
			json=json,
			files=files,
			headers=headers,
			auth=self.__auth,
			timeout=timeout,
		)


class MailServerManagerBase:
	"""Base class for Mail Server Managers."""

	def __init__(self, cluster_name: str) -> None:
		self.cluster_name = cluster_name


class MailServerDKIMManager(MailServerManagerBase):
	"""Class to manage DKIM keys on the Mail Server."""

	def create(self, domain_name: str, rsa_private_key: str) -> None:
		"""Creates a DKIM key on the cluster."""

		request_data = json.dumps(
			[
				{
					"type": "insert",
					"prefix": f"signature.rsa-{domain_name}",
					"values": [
						["report", "true"],
						["selector", get_dkim_selector("rsa")],
						["canonicalization", "relaxed/relaxed"],
						["private-key", rsa_private_key],
						["algorithm", "rsa-sha256"],
						["domain", domain_name],
					],
					"assert_empty": True,
				}
			]
		)
		create_request(
			cluster=self.cluster_name,
			method="POST",
			endpoint="/api/settings",
			request_data=request_data,
			execute_on_end="mail.mail_server.reload_request_cluster_servers",
		)

	def delete(self, domain_name: str) -> None:
		"""Deletes a DKIM key from the cluster."""

		request_data = json.dumps(
			[
				{
					"type": "clear",
					"prefix": f"signature.rsa-{domain_name}",
				}
			]
		)
		create_request(
			cluster=self.cluster_name,
			method="POST",
			endpoint="/api/settings",
			request_data=request_data,
		)


class MailServerDomainManager(MailServerManagerBase):
	"""Class to manage domains on the Mail Server."""

	def create(self, domain_name: str) -> None:
		"""Creates a domain on the cluster."""

		principal = Principal(name=domain_name, type="domain").__dict__
		create_request(
			cluster=self.cluster_name, method="POST", endpoint="/api/principal", request_data=principal
		)

	def delete(self, domain_name: str) -> None:
		"""Deletes a domain from the cluster."""

		create_request(cluster=self.cluster_name, method="DELETE", endpoint=f"/api/principal/{domain_name}")


class MailServerAccountManager(MailServerManagerBase):
	"""Class to manage accounts on the Mail Server."""

	def create(self, email: str, display_name: str, secret: str) -> None:
		"""Creates an account on the cluster."""

		principal = Principal(
			name=email,
			type="individual",
			description=display_name,
			secrets=[secret],
			emails=[email],
			roles=["user"],
		).__dict__
		create_request(
			cluster=self.cluster_name, method="POST", endpoint="/api/principal", request_data=principal
		)

	def update(self, email: str, display_name: str, new_secret: str, old_secret: str) -> None:
		"""Updates an account on the cluster."""

		request_data = [
			{
				"action": "set",
				"field": "description",
				"value": display_name,
			}
		]

		if old_secret != new_secret:
			request_data.extend(
				[
					{
						"action": "addItem",
						"field": "secrets",
						"value": new_secret,
					},
					{
						"action": "removeItem",
						"field": "secrets",
						"value": old_secret,
					},
				]
			)

		request_data = json.dumps(request_data)
		create_request(
			cluster=self.cluster_name,
			method="PATCH",
			endpoint=f"/api/principal/{email}",
			request_data=request_data,
		)

	def delete(self, email: str) -> None:
		"""Deletes an account from the cluster."""

		create_request(cluster=self.cluster_name, method="DELETE", endpoint=f"/api/principal/{email}")


class MailServerGroupManager(MailServerManagerBase):
	"""Class to manage groups on the Mail Server."""

	def create(self, email: str, display_name: str) -> None:
		"""Creates a group on the cluster."""

		principal = Principal(
			name=email,
			type="group",
			description=display_name,
			emails=[email],
			enabledPermissions=["email-send", "email-receive"],
		).__dict__
		create_request(
			cluster=self.cluster_name, method="POST", endpoint="/api/principal", request_data=principal
		)

	def update(self, email: str, display_name: str) -> None:
		"""Updates a group on the cluster."""

		request_data = json.dumps(
			[
				{
					"action": "set",
					"field": "description",
					"value": display_name,
				}
			]
		)
		create_request(
			cluster=self.cluster_name,
			method="PATCH",
			endpoint=f"/api/principal/{email}",
			request_data=request_data,
		)

	def delete(self, email: str) -> None:
		"""Deletes a group from the cluster."""

		create_request(cluster=self.cluster_name, method="DELETE", endpoint=f"/api/principal/{email}")


class MailServerAliasManager(MailServerManagerBase):
	"""Class to manage aliases on the Mail Server."""

	def create(self, email: str, alias: str) -> None:
		"""Creates an alias on the cluster."""

		request_data = json.dumps([{"action": "addItem", "field": "emails", "value": alias}])
		create_request(
			cluster=self.cluster_name,
			method="PATCH",
			endpoint=f"/api/principal/{email}",
			request_data=request_data,
		)

	def update(self, new_email: str, old_email: str, alias: str) -> None:
		"""Updates an alias on the cluster."""

		self.delete(old_email, alias)
		self.create(new_email, alias)

	def delete(self, email: str, alias: str) -> None:
		"""Deletes an alias from the cluster."""

		request_data = json.dumps([{"action": "removeItem", "field": "emails", "value": alias}])
		create_request(
			cluster=self.cluster_name,
			method="PATCH",
			endpoint=f"/api/principal/{email}",
			request_data=request_data,
		)


class MailServerMemberManager(MailServerManagerBase):
	"""Class to manage group members on the Mail Server."""

	def create(self, email: str, member: str, is_group: bool) -> None:
		"""Creates a group member on the cluster."""

		endpoint = None
		request_data = None
		if is_group:
			endpoint = f"/api/principal/{member}"
			request_data = json.dumps([{"action": "addItem", "field": "memberOf", "value": email}])
		else:
			endpoint = f"/api/principal/{email}"
			request_data = json.dumps([{"action": "addItem", "field": "members", "value": member}])

		create_request(
			cluster=self.cluster_name, method="PATCH", endpoint=endpoint, request_data=request_data
		)

	def update(self, new_email: str, old_email: str, member: str, is_group: bool) -> None:
		"""Updates a group member on the cluster."""

		self.delete(old_email, member, is_group)
		self.create(new_email, member, is_group)

	def delete(self, email: str, member: str, is_group: bool) -> None:
		"""Deletes a group member from the cluster."""

		endpoint = None
		request_data = None
		if is_group:
			endpoint = f"/api/principal/{member}"
			request_data = json.dumps([{"action": "removeItem", "field": "memberOf", "value": email}])
		else:
			endpoint = f"/api/principal/{email}"
			request_data = json.dumps([{"action": "removeItem", "field": "members", "value": member}])

		create_request(
			cluster=self.cluster_name, method="PATCH", endpoint=endpoint, request_data=request_data
		)


def get_mail_server_api(cluster_name: str) -> MailServerAPI:
	"""Returns an authenticated MailServerAPI instance."""

	cluster = frappe.get_cached_doc("Mail Cluster", cluster_name)
	api_key = cluster.get_password("api_key") if cluster.api_key else None

	return MailServerAPI(
		base_url=cluster.base_url,
		api_key=api_key,
		username=cluster.fallback_admin_user,
		password=cluster.get_password("fallback_admin_password"),
	)


# Execute on Start/End


def reload_request_cluster_servers(request: "MailServerRequest") -> None:
	from mail.mail.doctype.mail_cluster.mail_cluster import reload_servers_config

	try:
		reload_servers_config([request.cluster])
	except Exception:
		frappe.log_error(
			title=_("Error reloading {0} servers configuration").format(request.cluster),
			message=frappe.get_traceback(with_context=True),
		)
