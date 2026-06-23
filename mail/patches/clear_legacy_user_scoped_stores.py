import os
import shutil

from mail.storage import _get_blob_base_path, _get_data_base_path
from mail.storage.data_store import DataStore


def execute() -> None:
	"""Clear the data and blob stores after switching them from per-user to per-account keys.

	The stores used to be keyed by ``user:account_id``; they are now keyed by the bare
	``account_id`` so all users of a shared account hit the same cache. The old per-user
	directories/files are unreachable under the new keys, so we drop both stores once. They
	rebuild on demand — cached JMAP data (identities, mailboxes, emails, contacts, blobs) is
	re-fetched, and the email sync state simply re-initialises on the next pull.
	"""

	# Release any LMDB environments this process has open before removing their files.
	DataStore.close_all_envs()

	for base_path in (_get_data_base_path(), _get_blob_base_path()):
		if os.path.exists(base_path):
			shutil.rmtree(base_path, ignore_errors=True)
