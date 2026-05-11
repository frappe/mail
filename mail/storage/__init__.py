import os

import frappe
from frappe.utils import get_bench_path

from mail.storage.blob_store import BlobStore
from mail.storage.data_store import DataStore
from mail.utils import get_mail_config


def get_data_store(user: str, account_id: str | None = None) -> DataStore:
	"""Factory function to create a DataStore instance for the given user and account ID."""

	base_path = os.path.join(get_bench_path(), "sites", frappe.local.site, "private", "files", "data-store")
	key = f"{user}{DataStore.SEPARATOR}{account_id}" if account_id else user
	shard_count = get_mail_config("storage_shard_count")

	return DataStore(
		base_path=base_path,
		key=key,
		acquire_timeout=10,
		lock_timeout=60,
		max_retries=3,
		retry_delay=0.1,
		shard_count=shard_count,
	)


def get_blob_store(user: str, account_id: str | None = None) -> "BlobStore":
	"""Factory function to create a BlobStore instance for the given user and account ID."""

	base_path = os.path.join(get_bench_path(), "sites", frappe.local.site, "private", "files", "blob-store")
	key = f"{user}{BlobStore.SEPARATOR}{account_id}" if account_id else user
	shard_count = get_mail_config("storage_shard_count")

	return BlobStore(
		base_path=base_path,
		key=key,
		shard_count=shard_count,
	)
