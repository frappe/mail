from dataclasses import dataclass
from urllib.parse import urljoin

import requests


@dataclass
class JMAPConnectionInfo:
	"""
	Data class for storing JMAP connection information.

	Properties:
	- url: The base URL of the JMAP server.
	- username: The username for authentication.
	- password: The password for authentication.
	- timeout: A tuple specifying the connection and read timeouts for requests (default: (30.0, 60.0)).
	"""

	url: str
	username: str
	password: str
	timeout: tuple[float, float] = (30.0, 60.0)


class JMAPConnection:
	"""Manages the connection to a JMAP server, including discovery of server capabilities and sending requests."""

	def __init__(self, info: JMAPConnectionInfo) -> None:
		"""Initializes the JMAPConnection with the provided connection information."""

		self.__info = info
		self.__session = requests.Session()
		self.__session.auth = (self.__info.username, self.__info.password)
		self.__config = self._discover()

	def _discover(self) -> dict:
		"""Discovers the JMAP server configuration by making a GET request to the well-known JMAP endpoint."""

		url = urljoin(self.__info.url, "/.well-known/jmap")
		response = self.__session.get(
			url, headers={"Accept": "application/json"}, timeout=self.__info.timeout
		)
		raise_for_status(response)

		return response.json()

	@property
	def capabilities(self) -> dict:
		"""Returns the capabilities of the JMAP server."""

		return self.__config["capabilities"]

	@property
	def api_url(self) -> str:
		"""Returns the API URL of the JMAP server."""

		return self.__config["apiUrl"]

	@property
	def accounts(self) -> dict:
		"""Returns the accounts for the logged-in user."""

		return self.__config["accounts"]

	@property
	def primary_accounts(self) -> dict:
		"""Returns the primary accounts for the logged-in user."""

		return self.__config["primaryAccounts"]

	@property
	def download_url(self) -> str:
		"""Returns the download URL for the JMAP server."""

		return self.__config["downloadUrl"]

	@property
	def upload_url(self) -> str:
		"""Returns the upload URL for the JMAP server."""

		return self.__config["uploadUrl"]

	@property
	def event_source_url(self) -> str:
		"""Returns the event source URL for the JMAP server."""

		return self.__config["eventSourceUrl"]

	@property
	def state(self) -> dict:
		"""Returns the state of the JMAP server."""

		return self.__config["state"]

	def request(
		self,
		method: str,
		url: str,
		*,
		headers: dict | None = None,
		json: dict | None = None,
		data: bytes | str | None = None,
		params: dict | None = None,
		timeout: float | None = None,
		return_json: bool = True,
		**kwargs,
	) -> dict | bytes:
		"""Sends a request to the JMAP server with the specified parameters, and returns the response."""

		headers = headers or {}
		response = self.__session.request(
			method=method,
			url=url,
			headers=headers,
			json=json,
			data=data,
			params=params,
			timeout=timeout or self.__info.timeout,
			**kwargs,
		)

		raise_for_status(response)

		if return_json:
			return response.json()

		return response.content


def raise_for_status(response: requests.Response) -> None:
	"""Raises an HTTPError if the response status code indicates an error."""

	if not response.ok:
		raise requests.exceptions.HTTPError(f"Request failed: {response.text}")
