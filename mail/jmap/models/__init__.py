from dataclasses import dataclass
from typing import Literal


@dataclass
class EmailAddress:
	name: str
	email: str


@dataclass
class EmailRecipient(EmailAddress):
	type: Literal["to", "cc", "bcc"]


@dataclass
class EmailHeader:
	name: str
	value: str


@dataclass
class EmailAttachment:
	name: str
	type: str
	cid: str
	blob_id: str
	disposition: Literal["attachment", "inline"]


@dataclass
class EmailCreateModel:
	creation_id: str
	from_email: str
	recipients: list[EmailRecipient]
	from_name: str | None = None
	subject: str | None = None
	sent_at: str | None = None
	message_id: str | None = None
	reply_to: list[EmailAddress] | None = None
	in_reply_to: str | None = None
	headers: list[EmailHeader] | None = None
	text_body: str | None = None
	html_body: str | None = None
	attachments: list[EmailAttachment] | None = None
	raw_message: str | None = None
	existing_id: str | None = None
	save_as_draft: bool = False
	priority: int = 0
	destroy_after_submit: bool = False
	forwarded_id: str | None = None
	reply_to_id: str | None = None


@dataclass
class DataSourceObject:
	"""
	Dataclass to represent a data source object for uploads.
	Exactly one of `as_text`, `as_base64`, or `blob_id` must be provided.

	Parameters:
	- as_text: The data as a UTF-8 string.
	- as_base64: The data as a Base64-encoded string.
	- blob_id: The ID of the blob.
	- offset: The offset within the blob.
	- length: The length of the data within the blob.
	"""

	as_text: str | None = None
	as_base64: str | None = None
	blob_id: str | None = None
	offset: int | None = None
	length: int | None = None

	def __post_init__(self) -> None:
		inline_count = sum(v is not None for v in (self.as_text, self.as_base64))
		blob_used = self.blob_id is not None

		if blob_used and inline_count > 0:
			raise ValueError("DataSourceObject cannot have both blob_id and inline data.")

		if not blob_used and inline_count != 1:
			raise ValueError(
				"DataSourceObject must have exactly one of as_text or as_base64 when blob_id is not used."
			)

		if blob_used:
			if self.offset is not None and self.offset < 0:
				raise ValueError("Offset must be a non-negative integer.")

			if self.length is not None and self.length < 0:
				raise ValueError("Length must be a non-negative integer.")

			if self.offset is None:
				self.offset = 0

	def to_json(self) -> dict:
		"""Convert the DataSourceObject to a JSON-serializable dictionary."""

		if self.as_text is not None:
			return {"data:asText": self.as_text}

		if self.as_base64 is not None:
			return {"data:asBase64": self.as_base64}

		obj = {"blobId": self.blob_id}

		if self.offset is not None:
			obj["offset"] = self.offset

		if self.length is not None:
			obj["length"] = self.length

		return obj


@dataclass
class UploadObject:
	"""
	Dataclass to represent an upload object for Blob/upload.

	Parameters:
	- data: A list of DataSourceObject instances representing the data to be uploaded.
	- type: The MIME type of the data being uploaded (e.g., "text/plain", "image/jpeg").
	"""

	data: list[DataSourceObject]
	type: str | None = None

	def to_json(self) -> dict:
		"""Convert the UploadObject to a JSON-serializable dictionary."""

		obj = {"data": [d.to_json() for d in self.data]}

		if self.type is not None:
			obj["type"] = self.type

		return obj
