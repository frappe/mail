import hashlib
import os
from threading import RLock
from typing import ClassVar


class BaseStore:
	SEPARATOR: ClassVar[str] = ":"
	SHARD_DIR_PREFIX: ClassVar[str] = "shard-"
	_PROCESS_LOCKS: ClassVar[dict[str, RLock]] = {}
	_PROCESS_LOCKS_GUARD: ClassVar[RLock] = RLock()

	def __init__(
		self,
		base_path: str,
		key: str,
		shard_count: int = 1,
	) -> None:
		"""Initialize the storage with base path, key, and optional sharding parameters."""

		self.base_path = base_path
		self.key = key
		self.shard_count = max(1, shard_count)

		self.path = self._get_storage_path()
		os.makedirs(self.path, exist_ok=True)

		self._prefix = f"{self.key}{self.SEPARATOR}"

	def _get_storage_path(self) -> str:
		"""Return the shard path for this key, or the base path when sharding is disabled."""

		if self.shard_count == 1:
			return self.base_path

		shard = self._get_shard_index()
		return os.path.join(self.base_path, f"{self.SHARD_DIR_PREFIX}{shard:02d}")

	def _get_shard_index(self) -> int:
		"""Calculate the shard index for the current key based on its hash."""

		return int(hashlib.sha256(self.key.encode()).hexdigest(), 16) % self.shard_count

	def _get_process_lock(self, path: str | None = None) -> RLock:
		"""Return a process-local lock shared by all storage instances for the same path."""

		path = path or self.path

		with self._PROCESS_LOCKS_GUARD:
			lock = self._PROCESS_LOCKS.get(path)
			if lock is None:
				lock = RLock()
				self._PROCESS_LOCKS[path] = lock

			return lock

	def _get_prefix(self) -> str:
		"""Return the prefix for keys in this storage instance."""

		return self._prefix

	def _make_key(self, subkey: str) -> str:
		"""Construct the full key with prefix for storage."""

		return f"{self._get_prefix()}{subkey}"

	def _normalize_scan_key(self, subkey: str) -> str:
		"""Normalize a key returned from a scan by removing the prefix."""

		return subkey.removeprefix(self._get_prefix())
