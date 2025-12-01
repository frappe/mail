from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urljoin

import frappe
import requests
from frappe import _


@dataclass
class Principal:
	"""Dataclass to represent a principal."""

	name: str
	type: Literal["apiKey", "domain", "group", "individual", "list", "oauthClient", "role"]
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


class MailBackendAPI:
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
		timeout: int | tuple[int, int] = (5, 30),
	) -> Any:
		"""Makes an HTTP request to the Mail Backend API."""

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


def get_mail_backend_api(
	backend_type: Literal["Mail Cluster", "Mail Server"], backend_name: str
) -> MailBackendAPI:
	"""Returns an authenticated BackendAPI instance."""

	cluster_name = backend_name
	if backend_type == "Mail Server":
		cluster_name = frappe.db.get_value("Mail Server", backend_name, "cluster")

		if not cluster_name:
			frappe.throw(_("Mail Server {0} does not have a cluster.").format(backend_name))

	cluster = frappe.get_cached_doc("Mail Cluster", cluster_name)

	base_url = cluster.base_url
	if backend_type == "Mail Server":
		base_url = frappe.db.get_value("Mail Server", backend_name, "base_url")

		if not base_url:
			frappe.throw(_("Mail Server {0} does not have a base URL.").format(backend_name))

	api_key = cluster.get_password("api_key") if cluster.api_key else None

	return MailBackendAPI(
		base_url,
		api_key=api_key,
		username=cluster.fallback_admin_user,
		password=cluster.get_password("fallback_admin_password"),
	)
