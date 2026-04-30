import time
from dataclasses import dataclass
from typing import Any
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


class JMAPSessionManager:
	"""Manages the JMAP session information, allowing for retrieval, storage, and clearing of session data."""

	def __init__(self, get_session: callable, set_session: callable, clear_session: callable) -> None:
		"""Initializes the SessionManager with the provided functions for getting, setting, and clearing session data."""

		if not callable(get_session) or not callable(set_session) or not callable(clear_session):
			raise ValueError("All parameters must be callable functions.")

		self._get_session = get_session
		self._set_session = set_session
		self._clear_session = clear_session

	def get_session(self) -> Any | None:
		"""Retrieves the current session data, if available."""

		return self._get_session()

	def set_session(self, session: dict) -> None:
		"""Sets the session data."""

		self._set_session(session)

	def clear_session(self) -> None:
		"""Clears the session data."""

		self._clear_session()


class JMAPConnection:
	"""Manages the connection to a JMAP server, including discovery of server capabilities and sending requests."""

	def __init__(self, info: JMAPConnectionInfo, session_manager: JMAPSessionManager | None = None) -> None:
		"""Initializes the JMAPConnection with the provided connection information."""

		self.__info = info
		self.__session = requests.Session()
		self.__session.auth = (self.__info.username, self.__info.password)
		self.__session_manager = session_manager

		self._initialize_session()

	def _initialize_session(self) -> dict:
		"""Initializes the session by attempting to retrieve it from the session manager or performing session discovery."""

		if self.__session_manager:
			session = self.__session_manager.get_session()
			if session:
				self.session = session
				return

		self._session_discovery()

	def _session_discovery(self) -> None:
		"""Performs session discovery by sending a GET request to the JMAP server's well-known URL and storing the session information."""

		url = urljoin(self.__info.url, "/.well-known/jmap")
		response = self.__session.get(
			url, headers={"Accept": "application/json"}, timeout=self.__info.timeout
		)
		raise_for_status(response)

		self.session = response.json()
		self.session["timestamp"] = time.time()

		if self.__session_manager:
			self.__session_manager.set_session(self.session)

	@property
	def capabilities(self) -> dict:
		"""Returns the capabilities of the JMAP server."""

		return self.session["capabilities"]

	@property
	def api_url(self) -> str:
		"""Returns the API URL of the JMAP server."""

		return self.session["apiUrl"]

	@property
	def accounts(self) -> dict:
		"""Returns the accounts for the logged-in user."""

		return self.session["accounts"]

	@property
	def primary_accounts(self) -> dict:
		"""Returns the primary accounts for the logged-in user."""

		return self.session["primaryAccounts"]

	@property
	def download_url(self) -> str:
		"""Returns the download URL for the JMAP server."""

		return self.session["downloadUrl"]

	@property
	def upload_url(self) -> str:
		"""Returns the upload URL for the JMAP server."""

		return self.session["uploadUrl"]

	@property
	def event_source_url(self) -> str:
		"""Returns the event source URL for the JMAP server."""

		return self.session["eventSourceUrl"]

	@property
	def state(self) -> str:
		"""Returns the state of the JMAP server."""

		return self.session["state"]

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
		raise requests.exceptions.HTTPError(
			f"Request failed with status {response.status_code}: {response.text}", response=response
		)
