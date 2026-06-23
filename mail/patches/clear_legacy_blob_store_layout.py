import os
import shutil

from mail.storage import _get_blob_base_path


def execute() -> None:
	"""Drop the blob store after switching it to a per-account directory layout.

	Blobs used to be stored as flat files (one per ``account_id:blob_id`` key) directly in the
	blob-store base path, optionally split across ``shard-NN`` directories. They are now stored
	inside a directory named by the account ID, so the old files are unreachable under the new
	layout. The blob store is a cache, so we drop it once; it rebuilds on demand as blobs are
	re-fetched from the JMAP server.
	"""

	base_path = _get_blob_base_path()
	if os.path.exists(base_path):
		shutil.rmtree(base_path, ignore_errors=True)
