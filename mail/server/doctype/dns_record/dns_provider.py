from enum import Enum
from typing import Literal

from lexicon.client import Client


class DNSProviderEnum(str, Enum):
	AMAZON_ROUTE53 = "AmazonRoute53"
	DIGITALOCEAN = "DigitalOcean"
	CLOUDFLARE = "Cloudflare"
	HETZNER = "Hetzner"
	LINODE = "Linode"
	NAMECHEAP = "Namecheap"
	GODADDY = "GoDaddy"


DNSProviderLiteral = Literal[
	DNSProviderEnum.AMAZON_ROUTE53,
	DNSProviderEnum.DIGITALOCEAN,
	DNSProviderEnum.CLOUDFLARE,
	DNSProviderEnum.HETZNER,
	DNSProviderEnum.LINODE,
	DNSProviderEnum.NAMECHEAP,
	DNSProviderEnum.GODADDY,
]


DNS_PROVIDER_MAP = {
	DNSProviderEnum.AMAZON_ROUTE53: "route53",
	DNSProviderEnum.DIGITALOCEAN: "digitalocean",
	DNSProviderEnum.CLOUDFLARE: "cloudflare",
	DNSProviderEnum.HETZNER: "hetzner",
	DNSProviderEnum.LINODE: "linode",
	DNSProviderEnum.NAMECHEAP: "namecheap",
	DNSProviderEnum.GODADDY: "godaddy",
}


class DNSProvider:
	"""A DNS provider utility wrapper using Lexicon to interact with major DNS services."""

	def __init__(
		self,
		provider: DNSProviderLiteral,
		domain: str,
		access_key: str | None = None,
		access_secret: str | None = None,
		auth_key: str | None = None,
		auth_secret: str | None = None,
		username: str | None = None,
		token: str | None = None,
		client_ip: str | None = None,
		zone_id: str | None = None,
		private_zone: bool = False,
	) -> None:
		"""Initializes the DNSProvider with credentials and domain."""

		if provider not in DNS_PROVIDER_MAP:
			raise ValueError(f"Unsupported DNS Provider: {provider}")

		self.provider = DNS_PROVIDER_MAP[provider]
		self.domain = domain
		self.__access_key = access_key
		self.__access_secret = access_secret
		self.__auth_key = auth_key
		self.__auth_secret = auth_secret
		self.__username = username
		self.__token = token
		self.client_ip = client_ip
		self.zone_id = zone_id
		self.private_zone = private_zone

	def get_client(self, config: dict) -> Client:
		"""Internal helper to return a configured Lexicon client."""

		config.update(
			{
				"provider_name": self.provider,
				"domain": self.domain,
				"auth_access_key": self.__access_key,
				"auth_access_secret": self.__access_secret,
				"auth_key": self.__auth_key,
				"auth_secret": self.__auth_secret,
				"auth_username": self.__username,
				"auth_token": self.__token,
				"auth_client_ip": self.client_ip,
				"zone_id": self.zone_id,
				"private_zone": self.private_zone,
			}
		)
		client = Client(config)
		return client

	def create_dns_record(self, type: str, host: str, value: str, ttl: int, priority: int = 0) -> bool:
		"""Creates a new DNS record."""

		config = {
			"action": "create",
			"type": type,
			"name": host,
			"content": value,
			"ttl": ttl,
			"priority": priority,
		}
		client = self.get_client(config)
		return client.execute()

	def read_dns_records(self, type: str, host: str | None = None) -> list[dict]:
		"""Fetches DNS records matching type and optional host."""

		config = {
			"action": "list",
		}
		if type:
			config["type"] = type
		if host:
			config["name"] = host

		client = self.get_client(config)
		return client.execute()

	def update_dns_record(
		self,
		type: str,
		host: str,
		value: str,
		ttl: int,
		priority: int = 0,
		record_id: int | str | None = None,
	) -> bool:
		"""Updates an existing DNS record."""

		if not record_id:
			records = self.read_dns_records(type=type, host=host)
			if not records:
				raise ValueError(f"No record found for {host}")

			record_id = records[0]["id"]

		config = {
			"action": "update",
			"type": type,
			"name": host,
			"content": value,
			"ttl": ttl,
			"priority": priority,
			"identifier": record_id,
		}
		client = self.get_client(config)
		return client.execute()

	def delete_dns_record(self, type: str, host: str, delete_all: bool = False) -> bool:
		"""Deletes DNS record(s) for a given type and host."""

		records = self.read_dns_records(type=type, host=host)
		if not records:
			return True

		success = True

		for record in records if delete_all else [records[0]]:
			config = {
				"action": "delete",
				"type": type,
				"name": host,
				"identifier": record["id"],
			}
			client = self.get_client(config)
			try:
				client.execute()
			except Exception:
				success = False

		return success

	def create_or_update_dns_record(
		self, type: str, host: str, value: str, ttl: int, priority: int = 0
	) -> bool:
		"""Creates a new record if none exists; otherwise, updates the first matching record."""

		records = self.read_dns_records(type=type, host=host)
		if records:
			record_id = records[0]["id"]
			return self.update_dns_record(type, host, value, ttl, priority, record_id=record_id)
		else:
			return self.create_dns_record(type, host, value, ttl, priority)
