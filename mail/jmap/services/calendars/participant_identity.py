from typing import ClassVar

from mail.jmap.services.calendars.calendars import CalendarsService


class ParticipantIdentityService(CalendarsService):
	"""Service for handling participant identity-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "ParticipantIdentity"

	def create(self, participant_identities: list[dict]) -> dict:
		"""Public method to create participant identities, handling batching if the number of participant identities exceeds the server's maximum allowed in a single 'set' call."""

		result = {"created": {}, "notCreated": {}}
		for batch in self.create_batches(participant_identities, self.max_objects_in_set):
			payload = {}
			kwargs = {}
			for participant_identity in batch:
				payload[participant_identity["creation_id"]] = {
					"name": participant_identity["name"],
					"calendarAddress": f"mailto:{participant_identity['email']}",
				}

				if bool(participant_identity.get("is_default") or False):
					kwargs["onSuccessSetIsDefault"] = f"#{participant_identity['creation_id']}"

			response = self._create(payload, **kwargs)

			if method_responses := response.get("methodResponses"):
				result["created"].update(method_responses[0][1].get("created", {}))
				if not_created := method_responses[0][1].get("notCreated", {}):
					result["notCreated"].update(not_created)

		return result

	def get(self, ids: list[str] | None = None) -> list[dict]:
		"""Public method to get participant identities, handling batching if a list of ids is provided."""

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

	def update(self, participant_identities: list[dict]) -> dict:
		"""Public method to update participant identities, handling batching if the number of participant identities exceeds the server's maximum allowed in a single 'set' call."""

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(participant_identities, self.max_objects_in_set):
			payload = {}
			kwargs = {}
			for participant_identity in batch:
				payload[participant_identity["id"]] = {
					"name": participant_identity["name"],
					"calendarAddress": f"mailto:{participant_identity['email']}",
				}

				if bool(participant_identity.get("is_default") or False):
					kwargs["onSuccessSetIsDefault"] = participant_identity["id"]

			response = self._update(payload, **kwargs)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	def delete(self, ids: list[str]) -> dict:
		"""Public method to delete participant identities, handling batching if the number of participant identities exceeds the server's maximum allowed in a single 'set' call."""

		result = {"destroyed": [], "notDestroyed": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			response = self._delete(batch)

			if method_responses := response.get("methodResponses"):
				result["destroyed"].extend(method_responses[0][1].get("destroyed", []))
				if not_destroyed := method_responses[0][1].get("notDestroyed", {}):
					result["notDestroyed"].update(not_destroyed)

		return result

	def changes(self, since_state: str) -> dict:
		"""Public method to get changes to participant identities since a given state, handling batching if the number of changes exceeds the server's maximum allowed in a single 'changes' call."""

		response = self._changes(since_state)

		if method_responses := response.get("methodResponses"):
			return method_responses[0][1]

		return {}

	def get_default(self, raise_exception: bool = False) -> str | None:
		"""
		Returns the email address of the default participant identity, or None if no default participant identity is found.
		If raise_exception is True, raises a ValueError if no default participant identity is found.
		"""

		for identity in self.participant_identities:
			if identity.get("isDefault", False):
				return identity["calendarAddress"].lower().replace("mailto:", "")

		if raise_exception:
			raise ValueError("No default participant identity found.")
