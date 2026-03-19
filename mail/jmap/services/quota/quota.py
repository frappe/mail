from typing import ClassVar

from mail.jmap.services.core import CoreService


class QuotaService(CoreService):
	"""Service for handling quota-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "Quota"
	capabilities: ClassVar[list[str]] = ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:quota"]

	def __post_init__(self) -> None:
		"""Post-initialization to check if the JMAP server supports the Quota capability and raise an error if not."""

		super().__post_init__()

		if "urn:ietf:params:jmap:quota" not in self.connection.capabilities:
			raise NotImplementedError("The JMAP server does not support the Quota capability.")

	@property
	def primary_account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.connection.primary_accounts["urn:ietf:params:jmap:quota"]

	def query(
		self, filter: dict | None = None, position: int = 0, limit: int = 50, sort: list[dict] | None = None
	) -> dict:
		"""Public method to query quotas, handling batching if the number of results exceeds the server's maximum allowed in a single 'query' call."""

		ids = []
		total = None
		batch_size = min(limit, self.max_objects_in_get)

		while len(ids) < limit:
			response = self._query(filter, position, batch_size, sort, calculate_total=total is None)

			if method_responses := response.get("methodResponses"):
				query_response = method_responses[0][1]

				ids.extend(query_response.get("ids", []))

				if total is None:
					total = query_response.get("total", 0)

				if not query_response.get("hasMoreItems", False):
					break

				position += batch_size

		return {"ids": ids[:limit], "total": total}

	def get(self, ids: list[str] | None = None) -> list[dict]:
		"""Public method to get quotas, handling batching if a list of ids is provided."""

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

	def changes(self, since_state: str) -> dict:
		"""Public method to get quota changes since a given state."""

		response = self._changes(since_state)

		if method_responses := response.get("methodResponses"):
			return method_responses[0][1]

		return {}
