import os
import tempfile
from contextlib import suppress
from threading import RLock
from urllib.parse import quote, unquote

from mail.storage.base_store import BaseStore


class BlobStore(BaseStore):
	"""A simple blob storage backed by the local file system."""

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
			with open(path, "rb") as file:
				return file.read()
		except FileNotFoundError:
			return None

	def get(self, subkey: str, default: bytes | None = None) -> bytes | None:
		"""Retrieve a blob by key, returning a default if the key does not exist."""

		value = self._read_blob(self._get_blob_path(subkey))
		return value if value is not None else default

	def set(self, subkey: str, value: bytes | bytearray | memoryview) -> None:
		"""Store a blob by key using an atomic file replacement."""

		blob_path = self._get_blob_path(subkey)
		blob = bytes(value)
		process_lock = self._get_process_lock(blob_path)

		with process_lock:
			fd, temp_path = tempfile.mkstemp(dir=self.path)
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
		process_lock = self._get_process_lock(blob_path)

		with process_lock:
			with suppress(FileNotFoundError):
				os.remove(blob_path)

	def exists(self, subkey: str) -> bool:
		"""Check if a blob exists in the storage."""

		return os.path.exists(self._get_blob_path(subkey))

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
				if not entry.is_file() or not entry.name.startswith(encoded_prefix):
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
				if entry.is_file() and entry.name.startswith(encoded_prefix):
					count += 1

		return count

	def delete_all(self) -> None:
		"""Delete all blobs in the storage."""

		with os.scandir(self.path) as entries:
			for entry in entries:
				if entry.is_file():
					with suppress(FileNotFoundError):
						os.remove(entry.path)
