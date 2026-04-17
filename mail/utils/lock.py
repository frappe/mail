import time
from uuid import uuid7

import frappe
from frappe import _
from frappe.utils import cint
from redis.exceptions import WatchError

from mail.utils import get_mail_config


def acquire_lock(
	lockname: str, acquire_timeout: int | None = None, lock_timeout: int | None = None
) -> str | None:
	"""
	Acquire a distributed lock using Redis.
	Returns a unique identifier for the lock if acquired, else None.

	:param lockname: Unique lock name
	:param acquire_timeout: How long to wait for lock (0 = no wait), default: 0
	:param lock_timeout: TTL for lock in seconds, default: 10
	"""

	acquire_timeout = acquire_timeout or cint(get_mail_config("lock_acquire_timeout"))
	lock_timeout = lock_timeout or cint(get_mail_config("lock_timeout"))

	if lock_timeout <= 0:
		frappe.throw(_("Lock timeout must be greater than 0 seconds."))

	identifier = str(uuid7())
	lock_key = frappe.cache.make_key(f"lock:{lockname}")

	if acquire_timeout == 0:
		# nosemgrep: frappe-semgrep-rules.rules.frappe-cache-breaks-multitenancy
		if frappe.cache.set(lock_key, identifier, ex=lock_timeout, nx=True):
			return identifier
		else:
			return None

	end = time.time() + acquire_timeout
	while time.time() < end:
		# nosemgrep: frappe-semgrep-rules.rules.frappe-cache-breaks-multitenancy
		if frappe.cache.set(lock_key, identifier, ex=lock_timeout, nx=True):
			return identifier
		time.sleep(0.001)

	return None


def release_lock(lockname: str, identifier: str) -> bool:
	"""
	Release the lock only if it is held by the caller.
	"""

	lock_key = frappe.cache.make_key(f"lock:{lockname}")
	pipe = frappe.cache.pipeline(True)

	while True:
		try:
			pipe.watch(lock_key)
			value = pipe.get(lock_key)
			if value and value.decode() == identifier:
				pipe.multi()
				pipe.delete(lock_key)
				pipe.execute()
				return True

			pipe.unwatch()
			break
		except WatchError:
			continue

	return False
