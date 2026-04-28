import base64
import hashlib
import os
import time
from contextlib import contextmanager, suppress
from threading import RLock
from typing import Any, Literal

import frappe
import msgpack
import psutil
from rocksdict import BlockBasedOptions, Cache, DBCompressionType, Options, Rdict

from mail.storage.base_store import BaseStore
from mail.utils.lock import acquire_lock, release_lock


class DataStore(BaseStore):
	"""A simple key-value storage using RocksDB with write locking for concurrency control."""

	def __init__(
		self,
		base_path: str,
		key: str,
		acquire_timeout: int = 10,
		lock_timeout: int = 60,
		max_retries: int = 3,
		retry_delay: float = 0.1,
		shard_count: int = 1,
	) -> None:
		"""Initialize the storage with base path, key, and optional locking parameters."""

		super().__init__(
			base_path=base_path,
			key=key,
			shard_count=shard_count,
		)

		self.logger_context["store"] = "data"

		self.acquire_timeout = acquire_timeout
		self.lock_timeout = lock_timeout
		self.max_retries = max_retries
		self.retry_delay = retry_delay

		self.hash = base64.b32encode(hashlib.sha256(self.path.encode()).digest()).decode("ascii").lower()[:20]
		self._lock_key = f"rocksdict-lock-{self.hash}"

	@contextmanager
	def db_context(self, *, write: bool = False) -> Any:
		"""Context manager to handle serialized database access across threads and processes."""

		process_lock = self._get_process_lock()
		with process_lock:
			identifier = self._acquire_global_lock()
			db = None

			try:
				db = self._open_db()
				yield db

			finally:
				if db is not None:
					self._close_db(db)

				self._release_global_lock(identifier)

	def _get_process_lock(self) -> RLock:
		"""Return a process-local lock shared by all storage instances for the same path."""

		return super()._get_process_lock()

	def _acquire_global_lock(self) -> str:
		"""Acquire the cross-process lock that guards RocksDB connection creation and use."""

		identifier = None

		for attempt in range(self.max_retries):
			self.logger.debug(
				{
					**self.logger_context,
					"event": "attempting-glock-acquire",
					"lock_key": self._lock_key,
					"attempt": attempt + 1,
				}
			)

			identifier = acquire_lock(
				self._lock_key, acquire_timeout=self.acquire_timeout, lock_timeout=self.lock_timeout
			)
			if identifier:
				self.logger.debug(
					{
						**self.logger_context,
						"event": "glock-acquired",
						"lock_key": self._lock_key,
						"identifier": identifier,
					}
				)

				return identifier

			self.logger.warning(
				{
					**self.logger_context,
					"event": "glock-acquire-failed",
					"lock_key": self._lock_key,
					"attempt": attempt + 1,
				}
			)

			time.sleep(self.retry_delay * (2**attempt))

		raise TimeoutError(
			f"Could not acquire lock '{self._lock_key}' after {self.acquire_timeout} seconds and {self.max_retries} attempts."
		)

	def _release_global_lock(self, identifier: str) -> None:
		"""Release the cross-process lock that guards RocksDB connection creation and use."""

		self.logger.debug(
			{
				**self.logger_context,
				"event": "releasing-glock",
				"lock_key": self._lock_key,
				"identifier": identifier,
			}
		)

		release_lock(self._lock_key, identifier)

	def _open_db(self) -> Rdict:
		"""Open a RocksDB handle for the current operation."""

		self.logger.debug({**self.logger_context, "event": "opening-db", "path": self.path})

		return Rdict(self.path, options=self._get_options())

	def _close_db(self, db: Rdict) -> None:
		"""Close the RocksDB handle, ensuring all resources are released."""

		self.logger.debug({**self.logger_context, "event": "closing-db", "path": self.path})

		with suppress(Exception):
			db.close()

	def _get_options(self) -> Options:
		"""Configure RocksDB options for performance and reliability."""

		opts = Options()
		opts.create_if_missing(True)
		opts.set_keep_log_file_num(5)

		cpu_cores = os.cpu_count() or 2
		parallelism = min(max(cpu_cores, 2), 16)
		opts.increase_parallelism(parallelism)
		opts.set_max_background_jobs(parallelism)

		total_mem = psutil.virtual_memory().total or 4 * 1024 * 1024 * 1024
		block_cache_size = int(total_mem * 0.1)
		block_cache_size = max(64 * 1024 * 1024, min(block_cache_size, 2 * 1024 * 1024 * 1024))
		write_buffer_size = int(total_mem * 0.05)
		write_buffer_size = max(32 * 1024 * 1024, min(write_buffer_size, 256 * 1024 * 1024))

		opts.set_max_open_files(-1)
		opts.set_write_buffer_size(write_buffer_size)
		opts.set_max_write_buffer_number(3)
		opts.set_target_file_size_base(write_buffer_size)
		opts.set_max_bytes_for_level_base(write_buffer_size * 4)
		opts.set_compression_type(DBCompressionType.lz4())
		opts.set_use_fsync(False)

		table_opts = BlockBasedOptions()
		table_opts.set_block_cache(Cache(block_cache_size))
		table_opts.set_cache_index_and_filter_blocks(True)
		table_opts.set_pin_l0_filter_and_index_blocks_in_cache(True)
		opts.set_block_based_table_factory(table_opts)

		return opts

	def _serialize(self, value: Any) -> bytes:
		"""Serialize a value to bytes using msgpack."""

		return msgpack.packb(value, use_bin_type=True)

	def _deserialize(self, value: bytes) -> Any:
		"""Deserialize bytes back to a Python object using msgpack."""

		return msgpack.unpackb(value, raw=False)

	def _make_key(self, entity: Literal["states", "messages", "contact_cards"], subkey: str) -> str:
		"""Construct a full key by combining the entity type and subkey with the storage prefix."""

		subkey = f"{entity}{self.SEPARATOR}{subkey}"
		return super()._make_key(subkey)

	def get(
		self, entity: Literal["states", "messages", "contact_cards"], subkey: str, default: Any | None = None
	) -> Any | None:
		"""Retrieve a value by key, returning a default if the key does not exist."""

		with self.db_context() as db:
			value = db.get(self._make_key(entity, subkey))
			return self._deserialize(value) if value is not None else default

	def set(self, entity: Literal["states", "messages", "contact_cards"], subkey: str, value: Any) -> None:
		"""Store a value by key, serializing it before saving."""

		with self.db_context(write=True) as db:
			db.put(self._make_key(entity, subkey), self._serialize(value))

	def delete(self, entity: Literal["states", "messages", "contact_cards"], subkey: str) -> None:
		"""Delete a value by key."""

		with self.db_context(write=True) as db:
			db.delete(self._make_key(entity, subkey))

	def exists(self, entity: Literal["states", "messages", "contact_cards"], subkey: str) -> bool:
		"""Check if a key exists in the storage."""

		with self.db_context() as db:
			return db.get(self._make_key(entity, subkey)) is not None

	def get_many(
		self, entity: Literal["states", "messages", "contact_cards"], subkeys: list[str]
	) -> dict[str, Any | None]:
		"""Retrieve multiple values by a list of keys, returning a dictionary of key-value pairs."""

		if not subkeys:
			return {}

		keys = [self._make_key(entity, subkey) for subkey in subkeys]

		with self.db_context() as db:
			values = [db.get(k) for k in keys]

			result = {}
			for subkey, value in zip(subkeys, values, strict=False):
				result[subkey] = self._deserialize(value) if value is not None else None

			return result

	def set_many(self, entity: Literal["states", "messages", "contact_cards"], items: dict[str, Any]) -> None:
		"""Store multiple key-value pairs at once, serializing values before saving."""

		if not items:
			return

		with self.db_context(write=True) as db:
			for subkey, value in items.items():
				db.put(self._make_key(entity, subkey), self._serialize(value))

	def delete_many(self, entity: Literal["states", "messages", "contact_cards"], subkeys: list[str]) -> None:
		"""Delete multiple keys from the storage at once."""

		if not subkeys:
			return

		with self.db_context(write=True) as db:
			for key in subkeys:
				db.delete(self._make_key(entity, key))

	def scan(
		self, entity: Literal["states", "messages", "contact_cards"], prefix: str = ""
	) -> dict[str, Any]:
		"""Scan for all key-value pairs that start with a given prefix, returning a dictionary of results."""

		full_prefix = self._make_key(entity, prefix)
		result = {}

		with self.db_context() as db:
			it = db.iter()
			it.seek(full_prefix)

			while it.valid():
				key = it.key()
				if not key.startswith(full_prefix):
					break

				value = it.value()
				subkey = self._normalize_scan_key(key)
				result[subkey] = self._deserialize(value)

				it.next()

		return result

	def count(self, entity: Literal["states", "messages", "contact_cards"], prefix: str = "") -> int:
		"""Count the number of keys that start with a given prefix."""

		full_prefix = self._make_key(entity, prefix)
		count = 0

		with self.db_context() as db:
			it = db.iter()
			it.seek(full_prefix)

			while it.valid():
				key = it.key()
				if not key.startswith(full_prefix):
					break

				count += 1
				it.next()

		return count

	def delete_all(self, entity: Literal["states", "messages", "contact_cards"]) -> None:
		"""Delete all keys for a given entity type."""

		self.logger.info(
			{
				**self.logger_context,
				"user": frappe.session.user,
				"event": "deleting-all-keys",
				"entity": entity,
			}
		)

		with self.db_context(write=True) as db:
			it = db.iter()
			prefix = self._make_key(entity, "")
			it.seek(prefix)

			while it.valid():
				key = it.key()
				if not key.startswith(prefix):
					break

				db.delete(key)
				it.next()
