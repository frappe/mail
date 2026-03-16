from typing import ClassVar
from uuid import uuid7

from mail.jmap.services.mail.mail import MailService


class MailboxService(MailService):
	"""Service for handling mailbox-related operations based on the JMAP server capabilities."""

	type: ClassVar[str] = "Mailbox"

	def create(self, mailboxes: list[dict]) -> dict:
		"""Public method to create mailboxes, handling batching if the number of mailboxes exceeds the server's maximum allowed in a single 'set' call."""

		result = {"created": {}, "notCreated": {}}
		for batch in self.create_batches(mailboxes, self.max_objects_in_set):
			payload = {}
			for mailbox in batch:
				payload[mailbox["creation_id"]] = {
					"name": mailbox["name"],
					"role": mailbox.get("role") or None,
					"parentId": mailbox.get("parent_id") or None,
					"sortOrder": int(mailbox.get("sort_order") or 0),
					"isSubscribed": bool(mailbox.get("is_subscribed") or False),
				}

			response = self._create(payload)

			if method_responses := response.get("methodResponses"):
				result["created"].update(method_responses[0][1].get("created", {}))
				if not_created := method_responses[0][1].get("notCreated", {}):
					result["notCreated"].update(not_created)

		return result

	def get(self, ids: list[str] | None = None) -> list[dict]:
		"""Public method to get mailboxes, handling batching if a list of ids is provided."""

		results = []
		if ids:
			for batch in self.create_batches(ids, self.max_objects_in_get):
				response = self._get(batch)

				if method_responses := response.get("methodResponses"):
					results.extend(method_responses[0][1].get("list", []))
		else:
			response = self._get()
			if method_responses := response.get("methodResponses"):
				results.extend(method_responses[0][1].get("list", []))

		return results

	def update(self, mailboxes: list[dict]) -> dict:
		"""Public method to update mailboxes, handling batching if the number of mailboxes exceeds the server's maximum allowed in a single 'set' call."""

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(mailboxes, self.max_objects_in_set):
			payload = {}
			for mailbox in batch:
				payload[mailbox["id"]] = {
					"name": mailbox["name"],
					"role": mailbox.get("role") or None,
					"parentId": mailbox.get("parent_id") or None,
					"sortOrder": int(mailbox.get("sort_order") or 0),
					"isSubscribed": bool(mailbox.get("is_subscribed") or False),
				}

			response = self._update(payload)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	def delete(self, ids: list[str], remove_emails: bool = False) -> dict:
		"""Public method to delete mailboxes, handling batching if the number of mailbox IDs exceeds the server's maximum allowed in a single 'set' call."""

		result = {"destroyed": [], "notDestroyed": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			response = self._delete(batch, onDestroyRemoveEmails=remove_emails)

			if method_responses := response.get("methodResponses"):
				result["destroyed"].extend(method_responses[0][1].get("destroyed", []))
				if not_destroyed := method_responses[0][1].get("notDestroyed", {}):
					result["notDestroyed"].update(not_destroyed)

		return result

	def get_mailbox_id_by_role(
		self, role: str, create_if_not_exists: bool = False, raise_exception: bool = False
	) -> str | None:
		"""Return the mailbox ID for a given role, optionally creating it if missing."""

		def find_id(role: str) -> str | None:
			role = role.lower()
			for mailbox in self.mailboxes:
				mailbox_role = (mailbox.get("role") or "").lower()
				if mailbox_role == role:
					return mailbox["id"]

		if mailbox_id := find_id(role):
			return mailbox_id

		if not create_if_not_exists:
			if raise_exception:
				raise ValueError(f"No mailbox found with role '{role}'")

		creation_id = str(uuid7())
		mailbox = {
			"creation_id": creation_id,
			"name": role.title(),
			"role": role,
			"is_subscribed": True,
		}
		response = self.create([mailbox])

		if response.get("notCreated"):
			if raise_exception:
				raise ValueError(f"Failed to create mailbox with role '{role}'")

		self.invalidate_cache(self.user, key="mailboxes")

		return find_id(role)

	def get_mailbox_role_by_id(self, id: str, raise_exception: bool = False) -> str | None:
		"""Returns the mailbox role for the given ID."""

		for mailbox in self.mailboxes:
			if mailbox["id"] == id:
				return mailbox["role"]

		if raise_exception:
			raise ValueError(f"No mailbox found with ID '{id}'")

	def get_mailbox_name_by_id(self, id: str, raise_exception: bool = False) -> str | None:
		"""Returns the mailbox name for the given ID."""

		for mailbox in self.mailboxes:
			if id and mailbox["id"] == id:
				return mailbox["name"]

		if raise_exception:
			raise ValueError(f"No mailbox found with ID '{id}'")
