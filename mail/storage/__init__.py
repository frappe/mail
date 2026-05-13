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


def get_data_store(user: str, account_id: str | None = None) -> DataStore:
	"""Factory function to create a DataStore instance for the given user and account ID."""

	base_path = _get_data_base_path()
	key = f"{user}{DataStore.SEPARATOR}{account_id}" if account_id else user
	shard_count = get_config("storage_shard_count")

	return DataStore(
		base_path=base_path,
		key=key,
		acquire_timeout=10,
		lock_timeout=60,
		max_retries=3,
		retry_delay=0.1,
		shard_count=shard_count,
	)


@frappe.whitelist()
def destroy_data_store() -> None:
	"""Utility function to destroy the data store."""

	from mail.utils.user import is_system_manager

	if is_system_manager(frappe.session.user):
		base_path = _get_data_base_path()
		if os.path.exists(base_path):
			shutil.rmtree(base_path)


def get_blob_store(user: str, account_id: str | None = None) -> "BlobStore":
	"""Factory function to create a BlobStore instance for the given user and account ID."""

	base_path = _get_blob_base_path()
	key = f"{user}{BlobStore.SEPARATOR}{account_id}" if account_id else user
	shard_count = get_config("storage_shard_count")

	return BlobStore(
		base_path=base_path,
		key=key,
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
