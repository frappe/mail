import os
from collections import OrderedDict
from contextlib import contextmanager, suppress
from enum import Enum
from threading import RLock
from typing import Any, ClassVar
from urllib.parse import quote

import frappe
import lmdb
import msgpack

from mail.storage.base_store import BaseStore


class Entity(Enum):
	"""Defines the different types of entities that can be stored in the DataStore."""

	STATE = "state"

	IDENTITY = "identity"
	MAILBOX = "mailbox"
	EMAIL = "email"

	PARTICIPANT_IDENTITY = "participant_identity"
	CALENDAR = "calendar"
	EVENT = "event"

	ADDRESS_BOOK = "address_book"
	CONTACT_CARD = "contact_card"


def env_dirname(key: str) -> str:
	"""Return the filesystem-safe directory name for a store key's LMDB environment."""

	return quote(key, safe="")


class _EnvEntry:
	"""Tracks a cached LMDB environment and the number of in-flight transactions using it."""

	__slots__ = ("env", "refcount")

	def __init__(self, env: "lmdb.Environment") -> None:
		self.env = env
		self.refcount = 0


class DataStore(BaseStore):
	"""A key-value store backed by LMDB, with one environment per ``account`` key.

	The store is shared by every user with access to the account. LMDB natively supports
	concurrent multi-process access: many readers run lock-free via MVCC snapshots while a
	single writer briefly serializes on a robust mutex (and waits
	rather than failing). Environments are kept open and shared per process, so there is no
	per-operation open cost and no external locking layer.
	"""

	MAX_MSGPACK_BYTES = 25 * 1024 * 1024
	MAX_MSGPACK_COLLECTION_LEN = 2_00_000

	# Virtual address-space ceiling per environment. It is sparse (not preallocated) on 64-bit
	# systems, and grows automatically on MapFullError. Migration uses this same value.
	DEFAULT_MAP_SIZE = 2 * 1024 * 1024 * 1024

	# Best-effort per-process soft cap on simultaneously open environments. Before opening a
	# new environment, idle ones (no in-flight transactions) are closed least-recently-used
	# first. The cap may be temporarily exceeded under load when every cached environment is
	# busy, since an in-use environment is never force-closed.
	MAX_CACHED_ENVS = 128

	# Size of each environment's reader lock table. A reader slot is held per live process/thread
	# that has the environment open, and is shared across every process via lock.mdb, so the
	# default (126) is easily exhausted by many web + background workers on a hot account
	# (MDB_READERS_FULL). The table is a sparse file (~one page on disk until slots are used), so
	# a generous value is effectively free. Stale slots left by crashed/recycled workers are
	# reclaimed via reader_check().
	MAX_READERS = 2048

	_ENVS: ClassVar[OrderedDict[str, _EnvEntry]] = OrderedDict()
	_ENVS_GUARD: ClassVar[RLock] = RLock()

	def __init__(
		self,
		base_path: str,
		key: str,
		map_size: int | None = None,
		**_legacy: Any,
	) -> None:
		"""Initialize the store for the given base path and ``account`` key.

		``**_legacy`` absorbs parameters from the previous RocksDB implementation
		(acquire_timeout, lock_timeout, max_retries, retry_delay, shard_count) so existing
		callers keep working; they no longer have any effect.
		"""

		super().__init__(base_path=base_path, key=key, shard_count=1)

		self.logger_context["store"] = "data"
		self.map_size = map_size or self.DEFAULT_MAP_SIZE

	def _get_storage_path(self) -> str:
		"""Return the per-account LMDB environment directory for this key (no sharding)."""

		return os.path.join(self.base_path, env_dirname(self.key))

	def _open_env(self) -> "lmdb.Environment":
		"""Open the LMDB environment for this store's path."""

		self.logger.debug({**self.logger_context, "event": "opening-env", "path": self.path})

		env = lmdb.open(
			self.path,
			map_size=self.map_size,
			subdir=True,
			max_dbs=0,
			max_readers=self.MAX_READERS,
			readahead=False,
			meminit=False,
			writemap=False,
		)

		# Reclaim reader slots left behind by crashed or recycled workers. This runs whenever a
		# worker opens the environment, keeping the shared reader table from filling up over time.
		self._reader_check(env)
		return env

	def _reader_check(self, env: "lmdb.Environment") -> None:
		"""Reclaim stale reader-lock-table slots (from dead processes/threads). Best-effort."""

		try:
			reclaimed = env.reader_check()
			if reclaimed:
				self.logger.info(
					{
						**self.logger_context,
						"event": "reader-check",
						"path": self.path,
						"reclaimed": reclaimed,
					}
				)
		except Exception:
			self.logger.warning({**self.logger_context, "event": "reader-check-failed", "path": self.path})

	def _acquire_env(self) -> _EnvEntry:
		"""Return the cached environment for this path, opening it if needed, and mark it in use."""

		with self._ENVS_GUARD:
			entry = self._ENVS.get(self.path)
			if entry is None:
				self._evict_idle_envs()
				entry = _EnvEntry(self._open_env())
				self._ENVS[self.path] = entry

			entry.refcount += 1
			self._ENVS.move_to_end(self.path)
			return entry

	def _release_env(self) -> None:
		"""Mark this path's environment as no longer in use by the current operation."""

		with self._ENVS_GUARD:
			entry = self._ENVS.get(self.path)
			if entry is not None and entry.refcount > 0:
				entry.refcount -= 1

	@classmethod
	def close_all_envs(cls) -> None:
		"""Close every cached LMDB environment in this process.

		Intended for worker shutdown and tests. Must not be called while transactions are
		in flight; LMDB forbids opening the same environment twice in a process, so a fresh
		open afterwards is safe only once all handles are released.
		"""

		with cls._ENVS_GUARD:
			for entry in cls._ENVS.values():
				with suppress(Exception):
					entry.env.close()

			cls._ENVS.clear()

	def _evict_idle_envs(self) -> None:
		"""Close least-recently-used idle environments while over the cache cap."""

		while len(self._ENVS) >= self.MAX_CACHED_ENVS:
			victim_path = None
			for path, entry in self._ENVS.items():
				if entry.refcount == 0:
					victim_path = path
					break

			if victim_path is None:
				# Every cached environment is currently in use; nothing safe to evict.
				return

			entry = self._ENVS.pop(victim_path)
			self.logger.debug({**self.logger_context, "event": "evicting-env", "path": victim_path})
			with suppress(Exception):
				entry.env.close()

	def _grow_map(self) -> None:
		"""Double the map size of this path's environment after a MapFullError."""

		with self._ENVS_GUARD:
			entry = self._ENVS.get(self.path)
			if entry is None:
				return

			self.map_size = max(self.map_size * 2, self.DEFAULT_MAP_SIZE * 2)
			self.logger.warning(
				{**self.logger_context, "event": "growing-map", "path": self.path, "map_size": self.map_size}
			)
			entry.env.set_mapsize(self.map_size)

	@contextmanager
	def _txn(self, write: bool) -> Any:
		"""Yield an LMDB transaction on this store's environment."""

		entry = self._acquire_env()
		try:
			with self._begin(entry.env, write) as txn:
				yield txn
		finally:
			self._release_env()

	def _begin(self, env: "lmdb.Environment", write: bool) -> Any:
		"""Begin a transaction, reclaiming stale reader slots and retrying once on MDB_READERS_FULL."""

		try:
			return env.begin(write=write, buffers=False)
		except lmdb.ReadersFullError:
			self._reader_check(env)
			return env.begin(write=write, buffers=False)

	def _write(self, fn: Any) -> None:
		"""Run a write callback in a transaction, growing the map and retrying on MapFullError."""

		for _ in range(2):
			try:
				with self._txn(write=True) as txn:
					fn(txn)
				return
			except lmdb.MapFullError:
				self._grow_map()

		with self._txn(write=True) as txn:
			fn(txn)

	def _serialize(self, value: Any) -> bytes:
		"""Serialize a value to bytes using msgpack."""

		return msgpack.packb(value, use_bin_type=True)

	def _deserialize(self, value: bytes) -> Any:
		"""Deserialize bytes back to a Python object using msgpack."""

		if len(value) > self.MAX_MSGPACK_BYTES:
			raise ValueError("Serialized value exceeds allowed size limit")

		return msgpack.unpackb(
			value,
			raw=False,
			max_bin_len=self.MAX_MSGPACK_BYTES,
			max_str_len=self.MAX_MSGPACK_BYTES,
			max_ext_len=self.MAX_MSGPACK_BYTES,
			max_array_len=self.MAX_MSGPACK_COLLECTION_LEN,
			max_map_len=self.MAX_MSGPACK_COLLECTION_LEN,
		)

	def _make_key(self, entity: Entity, subkey: str) -> bytes:
		"""Construct a full key (with entity and storage prefix) as UTF-8 bytes."""

		subkey = f"{entity.value}{self.SEPARATOR}{subkey}"
		return super()._make_key(subkey).encode()

	def get(self, entity: Entity, subkey: str, default: Any | None = None) -> Any | None:
		"""Retrieve a value by key, returning a default if the key does not exist."""

		key = self._make_key(entity, subkey)
		with self._txn(write=False) as txn:
			value = txn.get(key)

		return self._deserialize(value) if value is not None else default

	def set(self, entity: Entity, subkey: str, value: Any) -> None:
		"""Store a value by key, serializing it before saving."""

		key = self._make_key(entity, subkey)
		data = self._serialize(value)
		self._write(lambda txn: txn.put(key, data))

	def delete(self, entity: Entity, subkey: str) -> None:
		"""Delete a value by key."""

		key = self._make_key(entity, subkey)
		self._write(lambda txn: txn.delete(key))

	def exists(self, entity: Entity, subkey: str) -> bool:
		"""Check if a key exists in the storage."""

		key = self._make_key(entity, subkey)
		with self._txn(write=False) as txn:
			return txn.get(key) is not None

	def get_many(self, entity: Entity, subkeys: list[str]) -> dict[str, Any | None]:
		"""Retrieve multiple values by a list of keys, returning a dictionary of key-value pairs."""

		if not subkeys:
			return {}

		keys = [(subkey, self._make_key(entity, subkey)) for subkey in subkeys]

		with self._txn(write=False) as txn:
			raw = [(subkey, txn.get(key)) for subkey, key in keys]

		return {subkey: self._deserialize(value) if value is not None else None for subkey, value in raw}

	def set_many(self, entity: Entity, items: dict[str, Any]) -> None:
		"""Store multiple key-value pairs at once, serializing values before saving."""

		if not items:
			return

		encoded = [
			(self._make_key(entity, subkey), self._serialize(value)) for subkey, value in items.items()
		]

		def _put_all(txn: Any) -> None:
			for key, data in encoded:
				txn.put(key, data)

		self._write(_put_all)

	def delete_many(self, entity: Entity, subkeys: list[str]) -> None:
		"""Delete multiple keys from the storage at once."""

		if not subkeys:
			return

		keys = [self._make_key(entity, subkey) for subkey in subkeys]

		def _delete_all(txn: Any) -> None:
			for key in keys:
				txn.delete(key)

		self._write(_delete_all)

	def scan(self, entity: Entity, prefix: str = "") -> dict[str, Any]:
		"""Scan for all key-value pairs that start with a given prefix, returning a dictionary of results."""

		full_prefix = self._make_key(entity, prefix)
		result = {}

		with self._txn(write=False) as txn:
			cursor = txn.cursor()
			if cursor.set_range(full_prefix):
				for key, value in cursor:
					if not key.startswith(full_prefix):
						break

					subkey = self._normalize_scan_key(key.decode())
					result[subkey] = self._deserialize(value)

		return result

	def count(self, entity: Entity, prefix: str = "") -> int:
		"""Count the number of keys that start with a given prefix."""

		full_prefix = self._make_key(entity, prefix)
		count = 0

		with self._txn(write=False) as txn:
			cursor = txn.cursor()
			if cursor.set_range(full_prefix):
				for key in cursor.iternext(keys=True, values=False):
					if not key.startswith(full_prefix):
						break

					count += 1

		return count

	def delete_all(self, entity: Entity) -> None:
		"""Delete all keys for a given entity type."""

		self.logger.info(
			{
				**self.logger_context,
				"user": frappe.session.user,
				"event": "deleting-all-keys",
				"entity": entity.value,
			}
		)

		full_prefix = self._make_key(entity, "")

		def _delete_prefix(txn: Any) -> None:
			# Delete in place via the cursor (O(1) memory) instead of materializing every key.
			# cursor.delete() removes the current entry and advances to the next one.
			cursor = txn.cursor()
			if cursor.set_range(full_prefix):
				while cursor.key().startswith(full_prefix):
					if not cursor.delete():
						break

		self._write(_delete_prefix)
