from typing import ClassVar

from mail.jmap.services.core import CoreService


class SieveScriptService(CoreService):
	"""Service for handling sieve script-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "SieveScript"
	capabilities: ClassVar[list[str]] = ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:sieve"]

	def __post_init__(self) -> None:
		"""Post-initialization to check if the JMAP server supports the Sieve capability and raise an error if not."""

		super().__post_init__()

		if "urn:ietf:params:jmap:sieve" not in self.connection.capabilities:
			raise NotImplementedError("The JMAP server does not support the Sieve capability.")

	@property
	def primary_account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.connection.primary_accounts["urn:ietf:params:jmap:sieve"]

	def create(self, sieve_scripts: list[dict]) -> dict:
		"""Public method to create sieve scripts, handling batching if the number of sieve scripts exceeds the server's maximum allowed in a single 'set' call."""

		result = {"created": {}, "notCreated": {}}
		for batch in self.create_batches(sieve_scripts, self.max_objects_in_set):
			payload = {}
			kwargs = {}
			for sieve_script in batch:
				content = sieve_script["content"]
				blob = self.upload_blob(content.encode("utf-8"), "application/sieve")
				payload[sieve_script["creation_id"]] = {
					"name": sieve_script["name"],
					"blobId": blob["blobId"],
				}

				if bool(sieve_script.get("is_active") or False):
					kwargs["onSuccessActivateScript"] = f"#{sieve_script['creation_id']}"

			response = self._create(payload, **kwargs)

			if method_responses := response.get("methodResponses"):
				result["created"].update(method_responses[0][1].get("created", {}))
				if not_created := method_responses[0][1].get("notCreated", {}):
					result["notCreated"].update(not_created)

		return result

	def get(self, ids: list[str] | None = None) -> list[dict]:
		"""Public method to get sieve scripts, handling batching if a list of ids is provided."""

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

	def update(self, sieve_scripts: list[dict], deactivate: bool = False) -> dict:
		"""Public method to update sieve scripts, handling batching if the number of sieve scripts exceeds the server's maximum allowed in a single 'set' call. Allows for optional deactivation of scripts."""

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(sieve_scripts, self.max_objects_in_set):
			payload = {}
			kwargs = {}
			for sieve_script in batch:
				content = sieve_script["content"]
				blob = self.upload_blob(content.encode("utf-8"), "application/sieve")
				payload[sieve_script["id"]] = {
					"name": sieve_script["name"],
					"blobId": blob["blobId"],
				}

				if bool(sieve_script.get("is_active") or False):
					kwargs["onSuccessActivateScript"] = sieve_script["id"]
				if deactivate:
					kwargs["onSuccessDeactivateScript"] = True

			if len(kwargs) > 1:
				raise ValueError(
					"Cannot specify both 'onSuccessActivateScript' and 'onSuccessDeactivateScript' at the same time."
				)

			response = self._update(payload, **kwargs)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	def delete(self, ids: list[str]) -> dict:
		"""Public method to delete sieve scripts, handling batching if the number of ids exceeds the server's maximum allowed in a single 'set' call."""

		result = {"destroyed": [], "notDestroyed": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			response = self._delete(batch)

			if method_responses := response.get("methodResponses"):
				result["destroyed"].extend(method_responses[0][1].get("destroyed", []))
				if not_destroyed := method_responses[0][1].get("notDestroyed", {}):
					result["notDestroyed"].update(not_destroyed)

		return result

	def query(self, filter: dict | None = None, position: int = 0, limit: int = 50) -> dict:
		"""Public method to query sieve scripts, handling batching if the number of results exceeds the server's maximum allowed in a single 'query' call."""

		_filter = {}
		filter = filter or {}
		for key in ["name", "isActive"]:
			if key in filter and filter[key] is not None:
				_filter[key] = filter[key]

		ids = []
		total = None
		batch_size = min(limit, self.max_objects_in_get)

		while len(ids) < limit:
			response = self._query(_filter, position, batch_size, calculate_total=total is None)

			if method_responses := response.get("methodResponses"):
				query_response = method_responses[0][1]

				ids.extend(query_response.get("ids", []))

				if total is None:
					total = query_response.get("total", 0)

				if not query_response.get("hasMoreItems", False):
					break

				position += batch_size

		return {"ids": ids[:limit], "total": total}

	def validate(self, content: str) -> dict:
		"""Public method to validate a sieve script's content."""

		blob = self.upload_blob(content.encode("utf-8"), "application/sieve")
		response = self._call(
			self.capabilities,
			[
				[
					f"{self.type}/validate",
					{
						"accountId": self.account_id,
						"blobId": blob["blobId"],
					},
					"0",
				]
			],
		)

		if method_responses := response.get("methodResponses"):
			return method_responses[0][1]

		return {}
