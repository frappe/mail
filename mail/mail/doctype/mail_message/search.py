import json
import re
from collections import defaultdict
from contextlib import suppress
from math import isclose

import frappe
from frappe.utils import cstr, strip_html_tags
from frappe.utils.synchronization import filelock
from redis.commands.search.field import TextField
from redis.commands.search.query import Query
from redis.exceptions import ResponseError

try:
	from redis.commands.search.index_definition import IndexDefinition
except ImportError:
	from redis.commands.search.indexDefinition import IndexDefinition


class EmailSearch:
	def __init__(self) -> None:
		self.ft = frappe.cache.ft("mail_message_idx")

	def build_index(self) -> None:
		self.drop_index()
		self.create_index()
		recipients = self.get_recipients()
		for doc in self.get_messages():
			doc["recipients"] = recipients.get(doc.name, [])
			self.index_doc(doc)

	def drop_index(self) -> None:
		"""Drops index."""

		with suppress(ResponseError):
			self.ft.dropindex(delete_documents=True)

	def create_index(self) -> None:
		"""Creates index."""

		definition = IndexDefinition(prefix=["mail_message"])
		schema = [
			TextField("subject", weight=12),
			TextField("html_body", weight=5),
			TextField("text_body", weight=5),
			TextField("from_name", weight=2),
			TextField("from_email", weight=2, no_stem=True),
			TextField("recipients", weight=2),
			TextField("account", no_stem=True),
		]
		self.ft.create_index(schema, definition=definition)
		self._index_exists = True

	def get_messages(self) -> list[dict]:
		"""Returns all email messages."""

		return frappe.get_all(
			"Email Message",
			filters={"destroyed": 0},
			fields=[
				"name",
				"subject",
				"html_body",
				"text_body",
				"account",
				"from_name",
				"from_email",
				"thread_id",
				"mailbox_id",
				"received_at",
			],
		)

	def get_recipients(self) -> dict:
		"""Returns all email message recipients."""

		recipients = frappe.get_all("Email Message Recipient", fields=["email", "display_name", "parent"])
		recipients_map = defaultdict(list)
		for r in recipients:
			recipients_map[r.pop("parent")].append(r)
		return recipients_map

	def index_doc(self, doc: dict) -> None:
		"""Indexes a single email message document."""

		if not self.index_exists():
			return

		key = f"mail_message:{doc.name}"

		doc.recipients = ", ".join(
			[
				f"{d.get('display_name')} <{d.get('email')}>" if d.get("display_name") else d.get("email")
				for d in doc.recipients
			]
		)

		mapping = {
			"subject": cstr(doc.subject),
			"html_body": cstr(strip_html_tags(doc.html_body or "")),
			"text_body": cstr(doc.text_body),
			"account": cstr(doc.account),
			"from_name": cstr(doc.from_name),
			"from_email": cstr(doc.from_email),
			"recipients": cstr(doc.recipients),
			"thread_id": cstr(doc.thread_id),
			"mailbox_id": cstr(doc.mailbox_id),
			"received_at": cstr(doc.received_at),
		}
		self.ft.add_document(key, replace=True, **mapping)

	def set_value(self, name: str, field: str, value: str) -> None:
		"""Update field value for indexed document."""

		frappe.cache.hset(f"mail_message:{name}", field, value)

	def index_exists(self):
		"""Checks if the email search index exists."""

		if hasattr(self, "_index_exists"):
			return self._index_exists
		self._index_exists = False
		with suppress(ResponseError):
			if isclose(int(self.ft.info()["num_docs"]), self.get_count(), rel_tol=0.1):
				self._index_exists = True
		return self._index_exists

	def get_count(self) -> int:
		"""Returns the count of email messages."""

		return frappe.db.count("Email Message", {"destroyed": 0})

	def search(self, input: str) -> dict:
		"""Searches the index based on the input string."""

		cleaned_input = re.sub(r"\s+", " ", re.sub(r"[\[\]{}<>+!\-*@.,'\"]", " ", input.strip())).lower()

		query_parts = []
		for word in cleaned_input.split():
			query_parts.append(f"({word}* | %{word}%)")

		fuzzy_query = " ".join(query_parts)

		query = (
			Query(f'@account:"{frappe.session.user}" {fuzzy_query}')
			.paging(0, 10)
			.summarize(fields=["html_body", "text_body"])
		)

		result = self.ft.search(query)
		out = frappe._dict(docs=[], total=result.total, duration=result.duration)

		for doc in result.docs:
			_doc = frappe._dict(doc.__dict__)
			_doc.id = doc.id.split(":", 1)[1]
			_doc.payload = json.loads(doc.payload) if doc.payload else None
			out.docs.append(_doc)

		return out

	def remove_docs(self, names: list[str]) -> None:
		if not self.index_exists():
			return

		for d in names:
			self.ft.delete_document(f"mail_message:{d}")


@filelock("email_search_indexing", timeout=300)
def build_index() -> None:
	"""Build the email search index."""

	frappe.cache.set_value("email_search_indexing_in_progress", True)
	search = EmailSearch()
	search.build_index()
	frappe.cache.set_value("email_search_indexing_in_progress", False)


def build_index_in_background() -> None:
	"""Build index if it doesn't exist and not already in progress."""

	search = EmailSearch()
	if not search.index_exists() and not frappe.cache.get_value("email_search_indexing_in_progress"):
		frappe.enqueue(build_index, queue="long")
