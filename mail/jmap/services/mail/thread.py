from typing import ClassVar

from mail.jmap.services.mail.mail import MailService


class ThreadService(MailService):
	"""Service for handling thread-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "Thread"

	def get(self, ids: list[str] | None = None) -> dict[str, list]:
		"""Public method to get threads, handling batching if a list of ids is provided."""

		result = {}
		if ids:
			for batch in self.create_batches(ids, self.max_objects_in_get):
				response = self._get(batch, properties=["emailIds"])

				if method_responses := response.get("methodResponses"):
					if threads := method_responses[0][1].get("list", []):
						result.update({thread["id"]: thread["emailIds"] for thread in threads})
		else:
			response = self._get(properties=["emailIds"])
			if method_responses := response.get("methodResponses"):
				if threads := method_responses[0][1].get("list", []):
					result.update({thread["id"]: thread["emailIds"] for thread in threads})

		return result
