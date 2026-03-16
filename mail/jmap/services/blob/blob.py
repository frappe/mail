from typing import ClassVar

from mail.jmap.models import UploadObject
from mail.jmap.services.core import CoreService


class BlobService(CoreService):
	"""Service for handling blob-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "Blob"
	capabilities: ClassVar[list[str]] = ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:blob"]

	def __post_init__(self) -> None:
		"""Post-initialization to check if the JMAP server supports the Blob capability and raise an error if not."""

		super().__post_init__()

		if "urn:ietf:params:jmap:blob" not in self.connection.capabilities:
			raise NotImplementedError("The JMAP server does not support the Blob capability.")

	@property
	def primary_account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.connection.primary_accounts["urn:ietf:params:jmap:blob"]

	def upload(self, blobs: dict[str, UploadObject]) -> dict:
		"""Public method to upload blobs, handling batching if the number of blobs exceeds the server's maximum allowed in a single 'set' call."""

		result = {"created": {}, "notCreated": {}}
		for batch in self.batch_dict(blobs, self.max_objects_in_set):
			payload = {creation_id: upload.to_json() for creation_id, upload in batch.items()}
			response = self._exec("upload", create=payload)

			if method_responses := response.get("methodResponses"):
				result["created"].update(method_responses[0][1].get("created", {}))
				if not_created := method_responses[0][1].get("notCreated", {}):
					result["notCreated"].update(not_created)

		return result

	def get(self, ids: list[str], properties: list[str]) -> list[dict]:
		"""Public method to retrieve blobs by their IDs, handling batching if the number of IDs exceeds the server's maximum allowed in a single 'get' call."""

		results = []
		for batch in self.create_batches(ids, self.max_objects_in_get):
			response = self._get(batch, properties=properties)

			if method_responses := response.get("methodResponses"):
				results.extend(method_responses[0][1].get("list", []))

		return results

	def lookup(self, ids: list[str], type_names: list[str]) -> list[dict]:
		"""Public method to look up blobs by their IDs and type names, handling batching if the number of IDs exceeds the server's maximum allowed in a single 'lookup' call."""

		results = []
		for batch in self.create_batches(ids, self.max_objects_in_get):
			response = self._exec("lookup", ids=batch, typeNames=type_names)

			if method_responses := response.get("methodResponses"):
				results.extend(method_responses[0][1].get("list", []))

		return results
