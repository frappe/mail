import requests
from typing import Literal
from abc import ABC, abstractmethod


class BaseDNSProvider(ABC):
	"""An abstract base class for DNS providers."""

	@abstractmethod
	def create_dns_record(
		self, domain: str, type: str, host: str, value: str, ttl: int
	) -> None:
		"""Creates a DNS record."""
		pass

	@abstractmethod
	def read_dns_records(self, domain: str):
		"""Reads DNS records for a domain."""
		pass

	@abstractmethod
	def update_dns_record(
		self, domain: str, record_id: int, type: str, host: str, value: str, ttl: int
	) -> None:
		"""Updates a DNS record."""
		pass

	@abstractmethod
	def delete_dns_record(self, domain: str, record_id: int) -> None:
		"""Deletes a DNS record."""
		pass


class DigitalOceanDNS(BaseDNSProvider):
	"""A DNS provider for DigitalOcean."""

	def __init__(self, token: str) -> None:
		"""Initializes the DigitalOceanDNS provider."""

		self.token = token
		self.api_base_url = "https://api.digitalocean.com/v2/domains"

	def _headers(self):
		"""Returns the headers for the API request."""

		return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

	def create_dns_record(
		self, domain: str, type: str, host: str, value: str, ttl: int
	) -> None:
		"""Creates a DNS record."""

		url = f"{self.api_base_url}/{domain}/records"
		data = {"type": type, "name": host, "data": value, "ttl": ttl}
		response = requests.post(url, headers=self._headers(), json=data)
		response.raise_for_status()
		print(f"DNS record created: {response.json()}")

	def read_dns_records(self, domain: str):
		"""Reads DNS records for a domain with pagination."""

		url = f"{self.api_base_url}/{domain}/records"
		all_records = []
		params = {"per_page": 100, "page": 1}

		while True:
			response = requests.get(url, headers=self._headers(), params=params)
			response.raise_for_status()
			data = response.json()
			records = data.get("domain_records", [])

			if not records:
				break

			all_records.extend(records)

			if len(records) < 100:
				break

			params["page"] += 1

		return all_records

	def update_dns_record(
		self, domain: str, record_id: int, type: str, host: str, value: str, ttl: int
	) -> None:
		"""Updates a DNS record."""

		url = f"{self.api_base_url}/{domain}/records/{record_id}"
		data = {"type": type, "name": host, "data": value, "ttl": ttl}
		response = requests.put(url, headers=self._headers(), json=data)
		response.raise_for_status()
		print(f"DNS record updated: {response.json()}")

	def delete_dns_record(self, domain: str, record_id: int) -> None:
		"""Deletes a DNS record."""

		url = f"{self.api_base_url}/{domain}/records/{record_id}"
		response = requests.delete(url, headers=self._headers())
		response.raise_for_status()
		print(f"DNS record deleted: {response.status_code == 204}")


class DNSProvider:
	"""A DNS provider class that uses a specific DNS provider."""

	def __init__(self, provider: Literal["DigitalOcean"], token: str) -> None:
		"""Initializes the DNS provider with the specified provider and token."""

		self.provider = self._get_dns_provider(provider, token)

	def _get_dns_provider(self, provider: str, token: str) -> BaseDNSProvider:
		"""Returns the DNS provider based on the provider name."""

		if provider == "DigitalOcean":
			return DigitalOceanDNS(token=token)
		else:
			raise ValueError(f"Unsupported DNS Provider: {provider}")

	def create_dns_record(
		self, domain: str, type: str, host: str, value: str, ttl: int
	) -> None:
		"""Creates a DNS record."""

		self.provider.create_dns_record(domain, type, host, value, ttl)

	def read_dns_records(self, domain: str):
		"""Reads DNS records for a domain."""

		return self.provider.read_dns_records(domain)

	def update_dns_record(
		self, domain: str, record_id: int, type: str, host: str, value: str, ttl: int
	) -> None:
		"""Updates a DNS record."""

		self.provider.update_dns_record(domain, record_id, type, host, value, ttl)

	def delete_dns_record(self, domain: str, record_id: int) -> None:
		"""Deletes a DNS record."""

		self.provider.delete_dns_record(domain, record_id)

	def create_or_update_dns_record(
		self, domain: str, type: str, host: str, value: str, ttl: int
	) -> None:
		"""Creates or updates a DNS record, handles pagination."""

		dns_records = self.read_dns_records(domain)

		# Check if the record already exists and update it
		for dns_record in dns_records:
			if dns_record["name"] == host and dns_record["type"] == type:
				self.update_dns_record(
					domain=domain,
					record_id=dns_record["id"],
					type=type,
					host=host,
					value=value,
					ttl=ttl,
				)
				break
		else:
			# Create a new record if no match is found
			self.create_dns_record(domain, type, host, value, ttl)

	def delete_dns_record_if_exists(self, domain: str, type: str, host: str) -> None:
		"""Deletes a DNS record if it exists, handles pagination."""

		dns_records = self.read_dns_records(domain)

		# Check for existing record and delete it
		for dns_record in dns_records:
			if dns_record["name"] == host and dns_record["type"] == type:
				self.delete_dns_record(domain, dns_record["id"])
				break
