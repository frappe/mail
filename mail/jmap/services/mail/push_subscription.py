from typing import ClassVar

from mail.jmap.services.mail.mail import MailService


class PushSubscriptionService(MailService):
	"""Service for handling push subscription-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "PushSubscription"

	def create(self, subscriptions: list[dict]) -> dict:
		"""Public method to create push subscriptions, handling batching if the number of subscriptions exceeds the server's maximum allowed in a single 'set' call."""

		result = {"created": {}, "notCreated": {}}
		for batch in self.create_batches(subscriptions, self.max_objects_in_set):
			payload = {}
			for subscription in batch:
				payload[subscription["creation_id"]] = {
					"deviceClientId": subscription["device_client_id"],
					"url": subscription["url"],
					"keys": subscription.get("keys") or None,
					"types": subscription["types"],
				}

			response = self._create(payload)

			if method_responses := response.get("methodResponses"):
				result["created"].update(method_responses[0][1].get("created", {}))
				if not_created := method_responses[0][1].get("notCreated", {}):
					result["notCreated"].update(not_created)

		return result

	def get(self, ids: list[str] | None = None) -> list[dict]:
		"""Public method to get push subscriptions, handling batching if a list of ids is provided."""

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

	def update(self, subscriptions: list[dict]) -> dict:
		"""Public method to update push subscriptions, handling batching if the number of subscriptions exceeds the server's maximum allowed in a single 'set' call."""

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(subscriptions, self.max_objects_in_set):
			payload = {}
			for subscription in batch:
				payload[subscription["id"]] = {}

				if verification_code := subscription.get("verification_code"):
					payload[subscription["id"]]["verificationCode"] = verification_code
				else:
					payload[subscription["id"]]["expires"] = subscription.get("expires")

			response = self._update(payload)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	def delete(self, ids: list[str]) -> dict:
		"""Public method to delete push subscriptions, handling batching if the number of IDs exceeds the server's maximum allowed in a single 'set' call."""

		result = {"destroyed": [], "notDestroyed": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			response = self._delete(batch)

			if method_responses := response.get("methodResponses"):
				result["destroyed"].extend(method_responses[0][1].get("destroyed", []))
				if not_destroyed := method_responses[0][1].get("notDestroyed", {}):
					result["notDestroyed"].update(not_destroyed)

		return result
