from typing import ClassVar

from mail.jmap.services.mail.mail import MailService


class IdentityService(MailService):
	"""Service for handling identity-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "Identity"

	def create(self, identities: list[dict]) -> dict:
		"""Public method to create identities, handling batching if the number of identities exceeds the server's maximum allowed in a single 'set' call."""

		result = {"created": {}, "notCreated": {}}
		for batch in self.create_batches(identities, self.max_objects_in_set):
			payload = {}
			for identity in batch:
				payload[identity["creation_id"]] = {
					"email": identity["email"],
					"name": identity.get("name"),
					"replyTo": identity.get("reply_to"),
					"bcc": identity.get("bcc"),
					"textSignature": identity.get("text_signature"),
					"htmlSignature": identity.get("html_signature"),
				}

			response = self._create(payload)

			if method_responses := response.get("methodResponses"):
				result["created"].update(method_responses[0][1].get("created", {}))
				if not_created := method_responses[0][1].get("notCreated", {}):
					result["notCreated"].update(not_created)

		return result

	def get(self, ids: list[str] | None = None) -> list[dict]:
		"""Public method to get identities, handling batching if a list of ids is provided."""

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

	def update(self, identities: list[dict]) -> dict:
		"""Public method to update identities, handling batching if the number of identities exceeds the server's maximum allowed in a single 'set' call."""

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(identities, self.max_objects_in_set):
			payload = {}
			for identity in batch:
				payload[identity["id"]] = {
					"name": identity.get("name"),
					"replyTo": identity.get("reply_to"),
					"bcc": identity.get("bcc"),
					"textSignature": identity.get("text_signature"),
					"htmlSignature": identity.get("html_signature"),
				}

			response = self._update(payload)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	def delete(self, ids: list[str]) -> dict:
		"""Public method to delete identities, handling batching if the number of IDs exceeds the server's maximum allowed in a single 'set' call."""

		result = {"destroyed": [], "notDestroyed": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			response = self._delete(batch)

			if method_responses := response.get("methodResponses"):
				result["destroyed"].extend(method_responses[0][1].get("destroyed", []))
				if not_destroyed := method_responses[0][1].get("notDestroyed", {}):
					result["notDestroyed"].update(not_destroyed)

		return result

	def get_identity_id_by_email(self, email: str, raise_exception: bool = False) -> str | None:
		"""Returns the identity ID for the given email, or raises an exception if not found and raise_exception is True."""

		for identity in self.identities:
			if identity["email"].lower() == email.lower():
				return identity["id"]

		if raise_exception:
			raise ValueError(f"No identity found for email: {email}")
