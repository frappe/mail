from typing import ClassVar
from uuid import uuid7

from mail.jmap.services.contacts.contacts import ContactsService
from mail.utils.dt import utcnow


class ContactCardService(ContactsService):
	"""Service for handling contact card-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "ContactCard"

	def create(self, contact_cards: list[dict]) -> dict:
		"""Public method to create contact cards, handling batching if the number of contact cards exceeds the server's maximum allowed in a single 'set' call."""

		result = {"created": {}, "notCreated": {}}
		for batch in self.create_batches(contact_cards, self.max_objects_in_set):
			payload = {}
			timestamp = utcnow()
			for contact_card in batch:
				payload[contact_card["creation_id"]] = {
					"@type": "Card",
					"version": "1.0",
					"uid": contact_card["creation_id"],
					"kind": contact_card.get("kind", "individual"),
					"name": self._get_name_map(contact_card.get("full_name")),
					"emails": self._get_emails_map(contact_card.get("emails")),
					"phones": self._get_phones_map(contact_card.get("phones")),
					"addresses": self._get_addresses_map(contact_card.get("addresses")),
					"addressBookIds": {id: True for id in contact_card["address_book_ids"]},
					"created": timestamp,
					"updated": timestamp,
				}

			response = self._create(payload)

			if method_responses := response.get("methodResponses"):
				result["created"].update(method_responses[0][1].get("created", {}))
				if not_created := method_responses[0][1].get("notCreated", {}):
					result["notCreated"].update(not_created)

		return result

	def get(self, ids: list[str] | None = None, properties: list[str] | None = None) -> list[dict]:
		"""Public method to get contact cards, handling batching if a list of ids is provided and allowing for optional properties to be specified."""

		properties = properties or [
			# --- JMAP-specific ---
			"id",
			"addressBookIds",
			"blobId",
			# --- JSContact core fields ---
			"uid",
			"kind",
			"prodId",
			"version",
			"created",
			"updated",
			"fullName",
			"name",
			"nickNames",
			"categories",
			"notes",
			"anniversaries",
			"urls",
			"relatedTo",
			"organizations",
			"titles",
			"roles",
			"emails",
			"phones",
			"addresses",
			"onlineServices",
			"preferredLanguages",
			"speakToAs",
			"gender",
			"timeZones",
			"photos",
			"members",
			"preferredContactChannels",
			"localizations",
			"extensions",
		]

		results = []
		if ids:
			for batch in self.create_batches(ids, self.max_objects_in_get):
				response = self._get(batch, properties=properties)

				if method_responses := response.get("methodResponses"):
					results.extend(method_responses[0][1].get("list", []))
		else:
			response = self._get(properties=properties)
			if method_responses := response.get("methodResponses"):
				results.extend(method_responses[0][1].get("list", []))

		return results

	def update(self, contact_cards: list[dict]) -> dict:
		"""Public method to update contact cards, handling batching if the number of contact cards exceeds the server's maximum allowed in a single 'set' call."""

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(contact_cards, self.max_objects_in_set):
			payload = {}
			for contact_card in batch:
				payload[contact_card["id"]] = {
					"kind": contact_card.get("kind", "individual"),
					"name": self._get_name_map(contact_card.get("full_name")),
					"emails": self._get_emails_map(contact_card.get("emails")),
					"phones": self._get_phones_map(contact_card.get("phones")),
					"addresses": self._get_addresses_map(contact_card.get("addresses")),
					"addressBookIds": {id: True for id in contact_card["address_book_ids"]},
					"updated": utcnow(),
				}

			response = self._update(payload)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	def delete(self, ids: list[str]) -> dict:
		"""Public method to delete contact cards, handling batching if the number of ids exceeds the server's maximum allowed in a single 'set' call."""

		result = {"destroyed": [], "notDestroyed": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			response = self._delete(batch)

			if method_responses := response.get("methodResponses"):
				result["destroyed"].extend(method_responses[0][1].get("destroyed", []))
				if not_destroyed := method_responses[0][1].get("notDestroyed", {}):
					result["notDestroyed"].update(not_destroyed)

		return result

	def query(
		self, filter: dict | None = None, position: int = 0, limit: int = 50, sort: list[dict] | None = None
	) -> dict:
		"""Public method to query contact cards, handling batching if the number of results exceeds the server's maximum allowed in a single 'query' call."""

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

	def changes(self, since_state: str) -> dict:
		"""Public method to get contact card changes since a given state."""

		response = self._changes(since_state)

		if method_responses := response.get("methodResponses"):
			return method_responses[0][1]

		return {}

	def update_address_book_ids(
		self,
		ids: list[str],
		add_address_book_id: str | None = None,
		remove_address_book_id: str | None = None,
		move_to_address_book_id: str | None = None,
	) -> dict:
		"""
		Updates addressBookIds for the provided contact cards.

		Behavior:
		- add_address_book_id: adds the contact to an address book
		- remove_address_book_id: removes the contact from an address book
		- add + remove: moves contact between address books (patch-based)
		- move_to_address_book_id: replaces addressBookIds entirely
		"""

		if move_to_address_book_id and (add_address_book_id or remove_address_book_id):
			raise ValueError(
				"Cannot specify 'move_to_address_book_id' together with 'add_address_book_id' or 'remove_address_book_id'."
			)

		if not any([add_address_book_id, remove_address_book_id, move_to_address_book_id]):
			raise ValueError(
				"At least one of 'add_address_book_id', 'remove_address_book_id', or 'move_to_address_book_id' must be specified."
			)

		result = {"updated": [], "notUpdated": {}}
		for batch in self.create_batches(ids, self.max_objects_in_set):
			if move_to_address_book_id:
				payload = {"addressBookIds": {move_to_address_book_id: True}, "updated": utcnow()}
			else:
				payload = {"updated": utcnow()}

				if add_address_book_id:
					payload[f"addressBookIds/{add_address_book_id}"] = True
				if remove_address_book_id:
					payload[f"addressBookIds/{remove_address_book_id}"] = None

			response = self._call(
				self.capabilities,
				[
					[
						f"{self.type}/set",
						{
							"accountId": self.account_id,
							"update": {id: payload for id in batch},
						},
						"0",
					]
				],
			)

			if method_responses := response.get("methodResponses"):
				result["updated"].extend(method_responses[0][1].get("updated", {}).keys())
				if not_updated := method_responses[0][1].get("notUpdated", {}):
					result["notUpdated"].update(not_updated)

		return result

	@staticmethod
	def _get_name_map(full_name: str | None = None) -> dict:
		"""Helper method to construct the 'name' property map for a contact card based on the provided full name."""

		if full_name:
			given, surname = full_name.split(" ", 1) if " " in full_name else (full_name, None)
			return {
				"@type": "Name",
				"full": full_name,
				"components": [{"kind": "given", "value": given}, {"kind": "surname", "value": surname}],
				"isOrdered": True,
			}

		return {}

	@staticmethod
	def _get_emails_map(emails: list[dict] | None = None) -> dict[str, dict] | None:
		"""Helper method to construct the 'emails' property map for a contact card based on the provided list of email dictionaries."""

		if emails:
			emails_map = {}
			for email in emails:
				emails_map[str(uuid7())] = {
					"address": email["address"],
					"label": email.get("label"),
					"contexts": {email["type"]: True},
				}

			return emails_map

	@staticmethod
	def _get_phones_map(phones: list[dict] | None = None) -> dict[str, dict] | None:
		"""Helper method to construct the 'phones' property map for a contact card based on the provided list of phone dictionaries."""

		if phones:
			phones_map = {}
			for phone in phones:
				phones_map[str(uuid7())] = {
					"number": phone["number"],
					"label": phone.get("label"),
					"contexts": {phone["type"]: True},
				}

			return phones_map

	@staticmethod
	def _get_addresses_map(addresses: list[dict] | None = None) -> dict[str, dict] | None:
		"""Helper method to construct the 'addresses' property map for a contact card based on the provided list of address dictionaries."""

		if addresses:
			counter = 0
			addresses_map = {}
			for address in addresses:
				components = []
				for field, key in {
					"street": "name",
					"locality": "locality",
					"region": "region",
					"postcode": "postcode",
					"country": "country",
				}.items():
					components.append({"kind": key, "value": address.get(field)})

				addresses_map[f"{counter}"] = {
					"components": components,
					"timeZone": address.get("time_zone"),
					"contexts": {address["type"]: True},
				}
				counter += 1

			return addresses_map
