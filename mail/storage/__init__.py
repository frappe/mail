import os
import shutil

import frappe
from frappe.utils import get_bench_path

from mail.storage.blob_store import BlobStore
from mail.storage.data_store import DataStore
from mail.utils import get_config


def _get_data_base_path() -> str:
	"""Helper function to get the base path for data storage."""

	return os.path.join(get_bench_path(), "sites", frappe.local.site, "private", "files", "data-store")


def _get_blob_base_path() -> str:
	"""Helper function to get the base path for blob storage."""

	return os.path.join(get_bench_path(), "sites", frappe.local.site, "private", "files", "blob-store")


def get_data_store(account_id: str) -> DataStore:
	"""Factory function to create a DataStore instance for the given JMAP account ID.

	The store is keyed solely by the account ID, so every user with access to a shared
	account reads and writes the same cache. LMDB serves concurrent access natively —
	many lock-free readers via MVCC snapshots and a single serialized writer — so multiple
	users (and worker processes) can hit the same account's store safely.
	"""

	base_path = _get_data_base_path()

	return DataStore(base_path=base_path, key=account_id)


@frappe.whitelist()
def destroy_data_store() -> None:
	"""Utility function to destroy the data store."""

	from mail.utils.user import is_system_manager

	if is_system_manager(frappe.session.user):
		base_path = _get_data_base_path()
		if os.path.exists(base_path):
			shutil.rmtree(base_path)


def get_blob_store(account_id: str) -> "BlobStore":
	"""Factory function to create a BlobStore instance for the given JMAP account ID.

	Keyed solely by the account ID, so the blob cache is shared across every user of an
	account. Writes are atomic (temp file + ``os.replace``) and reads open the file
	independently, so concurrent access from multiple users/processes is safe.
	"""

	base_path = _get_blob_base_path()
	shard_count = get_config("storage_shard_count")

	return BlobStore(
		base_path=base_path,
		key=account_id,
		shard_count=shard_count,
	)


@frappe.whitelist()
def destroy_blob_store() -> None:
	"""Utility function to destroy the blob store."""

	from mail.utils.user import is_system_manager

	if is_system_manager(frappe.session.user):
		base_path = _get_blob_base_path()
		if os.path.exists(base_path):
			shutil.rmtree(base_path)
