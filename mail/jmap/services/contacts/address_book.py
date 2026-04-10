from typing import ClassVar

from mail.jmap.services.contacts.contacts import ContactsService


class AddressBookService(ContactsService):
	"""Service for handling address book-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "AddressBook"

	def create(self, address_books: list[dict]) -> dict:
		"""Public method to create address books, handling batching if the number of address books exceeds the server's maximum allowed in a single 'set' call."""

		result = {"created": {}, "notCreated": {}}
		for batch in self.create_batches(address_books, self.max_objects_in_set):
			payload = {}
			kwargs = {}
			for address_book in batch:
				payload[address_book["creation_id"]] = {
					"name": address_book["name"],
					"description": address_book.get("description"),
					"sortOrder": int(address_book.get("sort_order") or 0),
					"isSubscribed": bool(address_book.get("is_subscribed") or False),
				}

				if bool(address_book.get("is_default") or False):
					kwargs["onSuccessSetIsDefault"] = f"#{address_book['creation_id']}"

			response = self._create(payload, **kwargs)

			if method_responses := response.get("methodResponses"):
				result["created"].update(method_responses[0][1].get("created", {}))
				if not_created := method_responses[0][1].get("notCreated", {}):
					result["notCreated"].update(not_created)

		return result

	def get(self, ids: list[str] | None = None) -> list[dict]:
		"""Public method to get address books, handling batching if a list of ids is provided."""

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

	def update(self, address_books: list[dict]) -> dict:
		"""Public method to update address books, handling batching if the number of address books exceeds the server's maximum allowed in a single 'set' call."""

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(address_books, self.max_objects_in_set):
			payload = {}
			kwargs = {}
			for address_book in batch:
				payload[address_book["id"]] = {
					"name": address_book["name"],
					"description": address_book.get("description"),
					"sortOrder": int(address_book.get("sort_order") or 0),
					"isSubscribed": bool(address_book.get("is_subscribed") or False),
				}

				if bool(address_book.get("is_default") or False):
					kwargs["onSuccessSetIsDefault"] = address_book["id"]

			response = self._update(payload, **kwargs)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	def delete(self, ids: list[str], remove_contents: bool = False) -> dict:
		"""Public method to delete address books, handling batching if the number of address book IDs exceeds the server's maximum allowed in a single 'set' call."""

		result = {"destroyed": [], "notDestroyed": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			response = self._delete(batch, onDestroyRemoveContents=remove_contents)

			if method_responses := response.get("methodResponses"):
				result["destroyed"].extend(method_responses[0][1].get("destroyed", []))
				if not_destroyed := method_responses[0][1].get("notDestroyed", {}):
					result["notDestroyed"].update(not_destroyed)

		return result

	def get_default(self, raise_exception: bool = False) -> str | None:
		"""Returns the ID of the default address book, or None if no default address book is found. If raise_exception is True, raises a ValueError if no default address book is found."""

		for address_book in self.address_books:
			if address_book.get("isDefault"):
				return address_book["id"]

		if raise_exception:
			raise ValueError("No default address book found.")
