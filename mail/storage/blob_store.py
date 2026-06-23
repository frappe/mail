import os
import stat
import tempfile
from contextlib import suppress
from threading import RLock
from urllib.parse import quote, unquote

import frappe

from mail.storage.base_store import BaseStore


class BlobStore(BaseStore):
	"""A blob storage backed by the local file system.

	Each account's blobs live in their own directory named by the account ID
	(``<base_path>/<account_id>/``); files inside are named by their encoded blob key.
	"""

	def __init__(
		self,
		base_path: str,
		key: str,
	) -> None:
		"""Initialize per-account blob storage rooted at ``<base_path>/<account_id>``."""

		super().__init__(base_path=base_path, key=key)

		self.logger_context["store"] = "blob"

		# Blobs are isolated per account by directory, so the on-disk file name is just the
		# (encoded) blob key — no account prefix is needed.
		self._prefix = ""

	def _get_storage_path(self) -> str:
		"""Store an account's blobs in their own directory, named by the account ID."""

		return os.path.join(self.base_path, self._encode_key(self.key))

	def _is_within_storage_path(self, path: str) -> bool:
		"""Return True when a path resolves within the configured storage directory."""

		storage_root = os.path.realpath(self.path)
		candidate = os.path.realpath(path)
		return os.path.commonpath([storage_root, candidate]) == storage_root

	def _get_process_lock(self, path: str) -> RLock:
		"""Return a process-local lock shared by all blob operations for the same path."""

		return super()._get_process_lock(path)

	def _encode_key(self, key: str) -> str:
		"""Encode the key into a filesystem-safe file name."""

		return quote(key, safe="")

	def _decode_key(self, key: str) -> str:
		"""Decode a filesystem-safe file name back to the original key."""

		return unquote(key)

	def _get_blob_path(self, subkey: str) -> str:
		"""Return the file path for the given blob key."""

		return os.path.join(self.path, self._encode_key(self._make_key(subkey)))

	def _read_blob(self, path: str) -> bytes | None:
		"""Read a blob from disk if it exists."""

		try:
			if not self._is_within_storage_path(path):
				return None

			stat_result = os.lstat(path)
			if not stat.S_ISREG(stat_result.st_mode):
				return None

			flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
			fd = os.open(path, flags)
			with os.fdopen(fd, "rb") as file:
				return file.read()
		except FileNotFoundError:
			return None
		except OSError:
			return None

	def get(self, subkey: str, default: bytes | None = None) -> bytes | None:
		"""Retrieve a blob by key, returning a default if the key does not exist."""

		value = self._read_blob(self._get_blob_path(subkey))
		return value if value is not None else default

	def set(self, subkey: str, value: bytes | bytearray | memoryview) -> None:
		"""Store a blob by key using an atomic file replacement."""

		blob_path = self._get_blob_path(subkey)
		if not self._is_within_storage_path(blob_path):
			raise ValueError("Invalid blob path")

		blob = bytes(value)
		process_lock = self._get_process_lock(blob_path)

		with process_lock:
			# Write the temp file in the base path (not the per-account directory) so it stays
			# outside what scan/count/delete_all walk, while remaining on the same filesystem
			# for an atomic os.replace into the account directory.
			fd, temp_path = tempfile.mkstemp(dir=self.base_path)
			try:
				with os.fdopen(fd, "wb") as file:
					file.write(blob)

				os.replace(temp_path, blob_path)
			except Exception:
				with suppress(FileNotFoundError):
					os.unlink(temp_path)
				raise

	def delete(self, subkey: str) -> None:
		"""Delete a blob by key."""

		blob_path = self._get_blob_path(subkey)
		if not self._is_within_storage_path(blob_path):
			return

		process_lock = self._get_process_lock(blob_path)

		with process_lock:
			with suppress(FileNotFoundError):
				os.remove(blob_path)

	def exists(self, subkey: str) -> bool:
		"""Check if a blob exists in the storage."""

		blob_path = self._get_blob_path(subkey)
		if not self._is_within_storage_path(blob_path):
			return False

		try:
			return stat.S_ISREG(os.lstat(blob_path).st_mode)
		except FileNotFoundError:
			return False

	def get_many(self, subkeys: list[str]) -> dict[str, bytes | None]:
		"""Retrieve multiple blobs by key."""

		if not subkeys:
			return {}

		result = {}
		for subkey in subkeys:
			result[subkey] = self._read_blob(self._get_blob_path(subkey))

		return result

	def set_many(self, items: dict[str, bytes | bytearray | memoryview]) -> None:
		"""Store multiple blobs."""

		if not items:
			return

		for subkey, value in items.items():
			self.set(subkey, value)

	def delete_many(self, subkeys: list[str]) -> None:
		"""Delete multiple blobs."""

		if not subkeys:
			return

		for key in subkeys:
			self.delete(key)

	def scan(self, prefix: str = "") -> dict[str, bytes]:
		"""Scan for all blobs whose keys start with the given prefix."""

		encoded_prefix = self._encode_key(self._make_key(prefix))
		result = {}

		with os.scandir(self.path) as entries:
			for entry in entries:
				if not entry.is_file(follow_symlinks=False) or not entry.name.startswith(encoded_prefix):
					continue

				value = self._read_blob(entry.path)
				if value is None:
					continue

				subkey = self._normalize_scan_key(self._decode_key(entry.name))
				result[subkey] = value

		return result

	def count(self, prefix: str = "") -> int:
		"""Count the number of blobs whose keys start with the given prefix."""

		encoded_prefix = self._encode_key(self._make_key(prefix))
		count = 0

		with os.scandir(self.path) as entries:
			for entry in entries:
				if entry.is_file(follow_symlinks=False) and entry.name.startswith(encoded_prefix):
					count += 1

		return count

	def delete_all(self) -> None:
		"""Delete all blobs in the storage for the current key prefix."""

		self.logger.info({**self.logger_context, "user": frappe.session.user, "event": "deleting-all-blobs"})

		encoded_prefix = self._encode_key(self._get_prefix())

		with os.scandir(self.path) as entries:
			for entry in entries:
				if entry.is_file(follow_symlinks=False) and entry.name.startswith(encoded_prefix):
					with suppress(FileNotFoundError):
						os.remove(entry.path)
