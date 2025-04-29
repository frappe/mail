import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urljoin

import frappe
import requests
from frappe import _

from mail.mail.doctype.mail_server_request.mail_server_request import create_mail_server_request
from mail.utils import get_dkim_selector

if TYPE_CHECKING:
	from mail.mail.doctype.mail_server_request.mail_server_request import MailServerRequest


@dataclass
class Principal:
	"""Dataclass to represent a principal."""

	name: str
	type: Literal["domain", "apiKey", "individual"]
	id: int = 0
	quota: int = 0
	description: str = ""
	secrets: str | list[str] = field(default_factory=list)
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
		self.__api_key = api_key
		self.__username = username
		self.__password = password
		self.__session = requests.Session()

		self.__auth = None
		self.__headers = {}
		if self.__api_key:
			self.__headers.update({"Authorization": f"Bearer {self.__api_key}"})
		else:
			if not self.__username or not self.__password:
				frappe.throw(_("API Key or Username and Password is required."))

			self.__auth = (self.__username, self.__password)

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
	) -> Any | None:
		"""Makes an HTTP request to the Mail Server API."""

		url = urljoin(self.base_url, endpoint)

		headers = headers or {}
		headers.update(self.__headers)

		if files:
			headers.pop("content-type", None)

		response = self.__session.request(
			method=method,
			url=url,
			params=params,
			data=data,
			headers=headers,
			files=files,
			auth=self.__auth,
			timeout=timeout,
			json=json,
		)

		return response


def get_mail_server_api(cluster_name: str) -> MailServerAPI:
	"""Returns an authenticated MailServerAPI instance."""

	cluster = frappe.get_cached_doc("Mail Cluster", cluster_name)
	api_key = cluster.get_password("api_key") if cluster.api_key else None

	return MailServerAPI(
		cluster.base_url,
		api_key=api_key,
		username=cluster.fallback_admin_user,
		password=cluster.get_password("fallback_admin_password"),
	)


def reload_request_cluster_servers(request: "MailServerRequest") -> None:
	from mail.mail.doctype.mail_cluster.mail_cluster import reload_servers_config

	try:
		reload_servers_config([request.cluster])
	except Exception as e:
		frappe.log_error(
			title=_("Error reloading {0} servers configuration").format(request.cluster), message=str(e)
		)


def create_dkim_key_on_cluster(cluster: str, domain_name: str, rsa_private_key: str) -> None:
	"""Creates a DKIM Key on the given cluster."""

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
	create_mail_server_request(
		cluster=cluster,
		method="POST",
		endpoint="/api/settings",
		request_data=request_data,
		execute_on_end="mail.mail_server.reload_request_cluster_servers",
	)


def delete_dkim_key_from_cluster(cluster: str, domain_name: str) -> None:
	"""Deletes a DKIM Key from the given cluster."""

	request_data = json.dumps(
		[
			{
				"type": "clear",
				"prefix": f"signature.rsa-{domain_name}",
			}
		]
	)
	create_mail_server_request(
		cluster=cluster,
		method="POST",
		endpoint="/api/settings",
		request_data=request_data,
	)


def create_domain_on_cluster(cluster: str, domain_name: str) -> None:
	"""Creates a domain on the given cluster."""

	principal = Principal(name=domain_name, type="domain").__dict__
	create_mail_server_request(
		cluster=cluster, method="POST", endpoint="/api/principal", request_data=principal
	)


def delete_domain_from_cluster(cluster: str, domain_name: str) -> None:
	"""Deletes a domain from the given cluster."""

	create_mail_server_request(cluster=cluster, method="DELETE", endpoint=f"/api/principal/{domain_name}")


def create_account_on_cluster(cluster: str, email: str, display_name: str, secret: str) -> None:
	"""Creates an account on the given cluster."""

	principal = Principal(
		name=email,
		type="individual",
		description=display_name,
		secrets=[secret],
		emails=[email],
		roles=["user"],
	).__dict__
	create_mail_server_request(
		cluster=cluster, method="POST", endpoint="/api/principal", request_data=principal
	)


def patch_account_on_cluster(
	cluster: str, email: str, display_name: str, new_secret: str, old_secret: str
) -> None:
	"""Patches an account on the given cluster."""

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
	create_mail_server_request(
		cluster=cluster, method="PATCH", endpoint=f"/api/principal/{email}", request_data=request_data
	)


def delete_account_from_cluster(cluster: str, email: str) -> None:
	"""Deletes an account from the given cluster."""

	create_mail_server_request(cluster=cluster, method="DELETE", endpoint=f"/api/principal/{email}")


def create_group_on_cluster(cluster: str, email: str, display_name: str) -> None:
	"""Creates a group on the given cluster."""

	principal = Principal(
		name=email,
		type="group",
		description=display_name,
		emails=[email],
		enabledPermissions=["email-send", "email-receive"],
	).__dict__
	create_mail_server_request(
		cluster=cluster, method="POST", endpoint="/api/principal", request_data=principal
	)


def patch_group_on_cluster(cluster: str, email: str, display_name: str) -> None:
	"""Patches a group on the given cluster."""

	request_data = json.dumps(
		[
			{
				"action": "set",
				"field": "description",
				"value": display_name,
			}
		]
	)
	create_mail_server_request(
		cluster=cluster, method="PATCH", endpoint=f"/api/principal/{email}", request_data=request_data
	)


def delete_group_from_cluster(cluster: str, email: str) -> None:
	"""Deletes a group from the given cluster."""

	delete_account_from_cluster(cluster, email)


def create_alias_on_cluster(cluster: str, email: str, alias: str) -> None:
	"""Creates an alias on the given cluster."""

	request_data = json.dumps([{"action": "addItem", "field": "emails", "value": alias}])
	create_mail_server_request(
		cluster=cluster, method="PATCH", endpoint=f"/api/principal/{email}", request_data=request_data
	)


def patch_alias_on_cluster(cluster: str, new_email: str, old_email: str, alias: str) -> None:
	"""Patches an alias on the given cluster."""

	delete_alias_from_cluster(cluster, old_email, alias)
	create_alias_on_cluster(cluster, new_email, alias)


def delete_alias_from_cluster(cluster: str, email: str, alias: str) -> None:
	"""Deletes an alias from the given cluster."""

	request_data = json.dumps([{"action": "removeItem", "field": "emails", "value": alias}])
	create_mail_server_request(
		cluster=cluster, method="PATCH", endpoint=f"/api/principal/{email}", request_data=request_data
	)


def create_member_on_cluster(cluster: str, email: str, member: str, is_group: bool) -> None:
	"""Creates a group member on the given cluster."""

	endpoint = None
	request_data = None
	if is_group:
		endpoint = f"/api/principal/{member}"
		request_data = json.dumps([{"action": "addItem", "field": "memberOf", "value": email}])
	else:
		endpoint = f"/api/principal/{email}"
		request_data = json.dumps([{"action": "addItem", "field": "members", "value": member}])

	create_mail_server_request(cluster=cluster, method="PATCH", endpoint=endpoint, request_data=request_data)


def patch_member_on_cluster(
	cluster: str, new_email: str, old_email: str, member: str, is_group: bool
) -> None:
	"""Patches a group member on the given cluster."""

	delete_member_from_cluster(cluster, old_email, member, is_group)
	create_member_on_cluster(cluster, new_email, member, is_group)


def delete_member_from_cluster(cluster: str, email: str, member: str, is_group: bool) -> None:
	"""Deletes a group member from the given cluster."""

	endpoint = None
	request_data = None
	if is_group:
		endpoint = f"/api/principal/{member}"
		request_data = json.dumps([{"action": "removeItem", "field": "memberOf", "value": email}])
	else:
		endpoint = f"/api/principal/{email}"
		request_data = json.dumps([{"action": "removeItem", "field": "members", "value": member}])

	create_mail_server_request(cluster=cluster, method="PATCH", endpoint=endpoint, request_data=request_data)
