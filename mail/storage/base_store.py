import os
from threading import RLock
from typing import ClassVar

from frappe.utils import random_string

from mail.utils.logger import get_storage_logger


class BaseStore:
	SEPARATOR: ClassVar[str] = ":"
	_PROCESS_LOCKS: ClassVar[dict[str, RLock]] = {}
	_PROCESS_LOCKS_GUARD: ClassVar[RLock] = RLock()

	def __init__(
		self,
		base_path: str,
		key: str,
	) -> None:
		"""Initialize the storage with the base path and key."""

		self.base_path = base_path
		self.key = key

		self.logger_context = {"req_id": random_string(10), "key": self.key}
		self.logger = get_storage_logger(self.logger_context)

		self.path = self._get_storage_path()
		os.makedirs(self.path, exist_ok=True)

		self._prefix = f"{self.key}{self.SEPARATOR}"

	def _get_storage_path(self) -> str:
		"""Return the storage path for this store; subclasses scope it per key."""

		return self.base_path

	def _get_process_lock(self, path: str | None = None) -> RLock:
		"""Return a process-local lock shared by all storage instances for the same path."""

		path = path or self.path

		self.logger.debug("acquiring-rlock", path=path)

		with self._PROCESS_LOCKS_GUARD:
			lock = self._PROCESS_LOCKS.get(path)
			if lock is None:
				lock = RLock()
				self._PROCESS_LOCKS[path] = lock

			self.logger.debug("rlock-acquired", path=path)
			return lock

	def _get_prefix(self) -> str:
		"""Return the prefix for keys in this storage instance."""

		return self._prefix

	def _make_key(self, subkey: str) -> str:
		"""Construct the full key with prefix for storage."""

		return f"{self._get_prefix()}{subkey}"

	def _normalize_scan_key(self, key: str) -> str:
		"""Normalize a key returned from a scan by removing the prefix."""

		return key.removeprefix(self._get_prefix())
