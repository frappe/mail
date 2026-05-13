from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urljoin

import frappe
import requests
from frappe import _

from mail.jmap.connection import raise_for_status
from mail.utils import get_config
from mail.utils.validation import validate_mail_config


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

		response = None

		try:
			response = self.__session.request(
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
			raise_for_status(response)

			return response
		except Exception:
			frappe.log_error(
				title=_("Mail Backend Request Failed"), message=frappe.get_traceback(with_context=False)
			)

			if response:
				frappe.throw(
					title=_("Backend Request Failed"),
					msg=_("Backend request failed with status code {0}. Check Error Log for details.").format(
						response.status_code
					),
				)
			else:
				frappe.throw(_("Backend request failed. Check Error Log for details."))


def get_mail_backend_api() -> MailBackendAPI:
	"""Returns an authenticated BackendAPI instance."""

	validate_mail_config()
	config = get_config()

	return MailBackendAPI(
		config["server_url"],
		api_key=config.get("api_key"),
		username=config.get("username"),
		password=config.get("password"),
	)
