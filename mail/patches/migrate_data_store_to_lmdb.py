import os
from contextlib import suppress

import frappe
import lmdb

from mail.storage import _get_data_base_path
from mail.storage.base_store import BaseStore
from mail.storage.data_store import DataStore, Entity, env_dirname

SEPARATOR = BaseStore.SEPARATOR
ENTITY_VALUES = {entity.value for entity in Entity}


def execute() -> None:
	"""Migrate the RocksDB-backed DataStore shards to per-account LMDB environments.

	The previous DataStore stored every account under a hash-sharded RocksDB directory
	(``shard-NN``), which only one process could open at a time. This copies every key into a
	dedicated LMDB environment per ``user:account`` key, where LMDB handles concurrent
	multi-process access natively.

	Keys and msgpack-encoded values are copied verbatim, so sync tokens are preserved and the
	next sync runs as an incremental delta (no full resync). The patch is idempotent and leaves
	the original RocksDB shards in place so the migration can be verified before cleanup.
	"""

	base_path = _get_data_base_path()
	if not os.path.isdir(base_path):
		return

	shard_dirs = sorted(
		entry.path
		for entry in os.scandir(base_path)
		if entry.is_dir() and entry.name.startswith(BaseStore.SHARD_DIR_PREFIX)
	)
	if not shard_dirs:
		return

	total = 0
	for shard_path in shard_dirs:
		total += _migrate_shard(base_path, shard_path)

	frappe.logger("mail.storage").info(
		{"event": "data-store-lmdb-migration-complete", "shards": len(shard_dirs), "keys": total}
	)


def _migrate_shard(base_path: str, shard_path: str) -> int:
	"""Copy every key from one RocksDB shard into its per-account LMDB environment."""

	from rocksdict import AccessType, Rdict

	try:
		db = Rdict(shard_path, access_type=AccessType.read_only())
	except Exception:
		# Fall back to a read-write open (e.g. when no prior LOCK exists); migration runs with
		# the site in maintenance mode, so an exclusive open is safe here.
		db = Rdict(shard_path)

	count = 0
	current_store_key = None
	env = None
	txn = None

	def close_current(commit: bool) -> None:
		# Commit the current account's transaction on success, or abort it on error so a failed
		# migration never leaves a partial account committed. Closing is best-effort and never
		# masks an in-flight exception.
		nonlocal env, txn, current_store_key
		try:
			if txn is not None:
				if commit:
					txn.commit()
				else:
					txn.abort()
		finally:
			if env is not None:
				with suppress(Exception):
					env.close()
			env, txn, current_store_key = None, None, None

	try:
		# RocksDB iterates in sorted key order, so all keys for one account are contiguous.
		for key, value in db.items():
			key_str = key if isinstance(key, str) else bytes(key).decode()
			store_key = _store_key_from(key_str)

			if store_key != current_store_key:
				close_current(commit=True)
				current_store_key = store_key
				env_path = os.path.join(base_path, env_dirname(store_key))
				os.makedirs(env_path, exist_ok=True)
				env = lmdb.open(
					env_path,
					map_size=DataStore.DEFAULT_MAP_SIZE,
					subdir=True,
					max_dbs=0,
					writemap=False,
				)
				txn = env.begin(write=True)

			txn.put(key_str.encode(), bytes(value))
			count += 1

		close_current(commit=True)
	except Exception:
		with suppress(Exception):
			close_current(commit=False)
		raise
	finally:
		db.close()

	return count


def _store_key_from(key: str) -> str:
	"""Derive the ``user:account`` store key from a full stored key.

	Stored keys are ``{user}:{account_id}:{entity}:{subkey}``. The second segment is the
	account id unless it is a known entity value (a legacy ``account_id=None`` store, whose
	keys are ``{user}:{entity}:{subkey}``).
	"""

	parts = key.split(SEPARATOR)
	if len(parts) >= 2 and parts[1] not in ENTITY_VALUES:
		return f"{parts[0]}{SEPARATOR}{parts[1]}"

	return parts[0]
