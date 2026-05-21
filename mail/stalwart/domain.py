import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

import frappe
from frappe import _

from mail.stalwart.cli import StalwartCLI


class CertificateManagementType(Enum):
	MANUAL = "Manual"
	AUTOMATIC = "Automatic"


@dataclass
class CertificateManagementProperties:
	acme_provider_id: str
	subject_alternative_names: list[str] | None = None


@dataclass
class CertificateManagement:
	type: CertificateManagementType = CertificateManagementType.MANUAL
	properties: CertificateManagementProperties | None = None

	def __post_init__(self) -> None:
		if self.type == CertificateManagementType.AUTOMATIC and not self.properties:
			raise ValueError("Properties must be provided for automatic certificate management.")
		elif self.type == CertificateManagementType.MANUAL and self.properties:
			raise ValueError("Properties should not be provided for manual certificate management.")

	def to_dict(self) -> dict:
		if self.type == CertificateManagementType.MANUAL:
			return {"@type": self.type.value}
		else:
			return {
				"@type": self.type.value,
				"acmeProviderId": self.properties.acme_provider_id,
				"subjectAlternativeNames": self.properties.subject_alternative_names,
			}


class DkimManagementType(Enum):
	MANUAL = "Manual"
	AUTOMATIC = "Automatic"


class DkimSignatureType(Enum):
	DKIM1_ED25519_SHA256 = "Dkim1Ed25519Sha256"
	DKIM_RSA_SHA256 = "Dkim1RsaSha256"


@dataclass
class DkimManagementProperties:
	algorithms: list[DkimSignatureType] = field(
		default_factory=lambda: [
			DkimSignatureType.DKIM1_ED25519_SHA256,
			DkimSignatureType.DKIM_RSA_SHA256,
		]
	)
	selector_template: str = "v{version}-{algorithm}-{date-%Y%m%d}"
	rotate_after: int = 90 * 24 * 60 * 60 * 1000
	retire_after: int = 7 * 24 * 60 * 60 * 1000
	delete_after: int = 30 * 24 * 60 * 60 * 1000


@dataclass
class DkimManagement:
	type: DkimManagementType = DkimManagementType.AUTOMATIC
	properties: DkimManagementProperties = field(default_factory=DkimManagementProperties)

	def __post_init__(self) -> None:
		if self.type == DkimManagementType.AUTOMATIC and not self.properties:
			raise ValueError("Properties must be provided for automatic DKIM management.")
		elif self.type == DkimManagementType.MANUAL and self.properties:
			raise ValueError("Properties should not be provided for manual DKIM management.")

	def to_dict(self) -> dict:
		if self.type == DkimManagementType.MANUAL:
			return {"@type": self.type.value}
		else:
			return {
				"@type": self.type.value,
				"algorithms": {algorithm.value: True for algorithm in self.properties.algorithms}
				if self.properties.algorithms
				else {},
				"selectorTemplate": self.properties.selector_template,
				"rotateAfter": self.properties.rotate_after,
				"retireAfter": self.properties.retire_after,
				"deleteAfter": self.properties.delete_after,
			}


class DnsManagementType(Enum):
	MANUAL = "Manual"
	AUTOMATIC = "Automatic"


class DnsRecordType(Enum):
	DKIM = "dkim"
	TLSA = "tlsa"
	SPF = "spf"
	MX = "mx"
	DMARC = "dmarc"
	SRV = "srv"
	MTA_STS = "mtaSts"
	TLS_RPT = "tlsRpt"
	CAA = "caa"
	AUTO_CONFIG = "autoConfig"
	AUTO_CONFIG_LEGACY = "autoConfigLegacy"
	AUTO_DISCOVER = "autoDiscover"


@dataclass
class DnsManagementProperties:
	dns_server_id: str
	origin: str | None = None
	publish_records: list[DnsRecordType] = field(
		default_factory=lambda: [
			DnsRecordType.DKIM,
			DnsRecordType.SPF,
			DnsRecordType.MX,
			DnsRecordType.DMARC,
			DnsRecordType.SRV,
			DnsRecordType.MTA_STS,
			DnsRecordType.TLS_RPT,
			DnsRecordType.CAA,
			DnsRecordType.AUTO_CONFIG,
			DnsRecordType.AUTO_CONFIG_LEGACY,
			DnsRecordType.AUTO_DISCOVER,
		]
	)


@dataclass
class DnsManagement:
	type: DnsManagementType = DnsManagementType.MANUAL
	properties: DnsManagementProperties | None = None

	def __post_init__(self) -> None:
		if self.type == DnsManagementType.AUTOMATIC and not self.properties:
			raise ValueError("Properties must be provided for automatic DNS management.")
		elif self.type == DnsManagementType.MANUAL and self.properties:
			raise ValueError("Properties should not be provided for manual DNS management.")

	def to_dict(self) -> dict:
		if self.type == DnsManagementType.MANUAL:
			return {"@type": self.type.value}
		else:
			return {
				"@type": self.type.value,
				"dnsServerId": self.properties.dns_server_id,
				"origin": self.properties.origin,
				"publishRecords": [record.value for record in self.properties.publish_records],
			}


class SubAddressingType(Enum):
	DISABLED = "Disabled"
	ENABLED = "Enabled"
	CUSTOM = "Custom"


@dataclass
class SubAddressingCustom:
	custom_rule: str


@dataclass
class SubAddressing:
	type: SubAddressingType = SubAddressingType.ENABLED
	properties: SubAddressingCustom | None = None

	def __post_init__(self) -> None:
		if self.type == SubAddressingType.CUSTOM and not self.properties:
			raise ValueError("Properties must be provided for custom sub-addressing.")
		elif self.type != SubAddressingType.CUSTOM and self.properties:
			raise ValueError("Properties should not be provided for non-custom sub-addressing.")

	def to_dict(self) -> dict:
		if self.type != SubAddressingType.CUSTOM:
			return {"@type": self.type.value}
		else:
			return {
				"@type": self.type.value,
				"customRule": self.properties.custom_rule,
			}


@dataclass
class Domain:
	name: str
	aliases: list[str] | None = None
	is_enabled: bool = True
	description: str | None = None
	certificate_management: CertificateManagement = field(default_factory=CertificateManagement)
	dkim_management: DkimManagement = field(default_factory=DkimManagement)
	dns_management: DnsManagement = field(default_factory=DnsManagement)
	catch_all_address: str | None = None
	sub_addressing: SubAddressing = field(default_factory=SubAddressing)
	allow_relaying: bool = False
	report_address_uri: str | None = "mailto:postmaster"

	def to_dict(self) -> dict:
		return {
			"name": self.name,
			"aliases": {alias: True for alias in self.aliases} if self.aliases else {},
			"isEnabled": self.is_enabled,
			"description": self.description,
			"certificateManagement": self.certificate_management.to_dict(),
			"dkimManagement": self.dkim_management.to_dict(),
			"dnsManagement": self.dns_management.to_dict(),
			"catchAllAddress": self.catch_all_address,
			"subAddressing": self.sub_addressing.to_dict(),
			"allowRelaying": self.allow_relaying,
			"reportAddressUri": self.report_address_uri,
		}


class DomainService(StalwartCLI):
	DEFAULT_FIELDS: ClassVar[list[str]] = ["id", "isEnabled", "name", "description"]
	ALLOWED_FILTER_KEYS: ClassVar[set[str]] = {"text", "name"}

	@classmethod
	def _resolved_fields(cls, fields: list[str] | None) -> list[str]:
		return fields if isinstance(fields, list) else cls.DEFAULT_FIELDS

	@classmethod
	def _append_filters(cls, commands: list[str], filters: dict[str, str]) -> None:
		for key, value in filters.items():
			if key in cls.ALLOWED_FILTER_KEYS:
				commands.extend(["--where", f"{key}={value}"])
			else:
				frappe.throw(
					_("Invalid filter key: {0}. Allowed keys are: {1}").format(
						key, ", ".join(cls.ALLOWED_FILTER_KEYS)
					)
				)

	@staticmethod
	def _parse_query_output(output: str) -> list[dict]:
		if not output:
			return []

		return [json.loads(domain) for domain in output.splitlines()]

	def get(self, id: str, fields: list[str] | None = None) -> dict:
		"""Fetches a domain by ID from the Stalwart server, selecting specific fields if provided."""

		fields = self._resolved_fields(fields)

		commands = ["get", "Domain", id]

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			if response["output"]:
				return json.loads(response["output"])
			else:
				frappe.throw(title=_("Domain not found"), msg=_("Domain with ID {0} not found.").format(id))
		else:
			frappe.throw(title=_("Failed to fetch domain"), msg=response["output"] or response["error"])

	def get_all(self, filters: dict[str, str] | None = None, fields: list[str] | None = None) -> list[dict]:
		"""Fetches all domains from the Stalwart server, applying optional filters and selecting specific fields."""

		filters = filters or {}
		fields = self._resolved_fields(fields)

		commands = ["query", "Domain"]

		if filters:
			self._append_filters(commands, filters)

		if fields:
			commands.extend(["--fields", ",".join(fields)])

		commands.append("--json")
		response = self.run(commands)

		if response["success"]:
			return self._parse_query_output(response["output"])
		else:
			frappe.throw(title=_("Failed to fetch domains"), msg=response["output"] or response["error"])

	def create(self, domain: "Domain") -> str:
		"""Creates a new domain on the Stalwart server with the provided domain data."""

		def _parse_domain_id(output: str) -> str | None:
			match = re.search(r"Created Domain\s+(\S+)", output)
			if match:
				return match.group(1)

		domain_data = domain.to_dict()
		domain_json = json.dumps(domain_data)
		response = self.run(["create", "Domain", "--json", domain_json])

		if not response["success"]:
			frappe.throw(title=_("Failed to create domain"), msg=response["output"] or response["error"])

		domain_id = _parse_domain_id(response["output"])
		if not domain_id:
			frappe.throw(
				title=_("Failed to parse domain ID"),
				msg=_("Could not extract the created domain ID from the response."),
			)

		return domain_id

	def delete(self, ids: list[str]) -> None:
		"""Deletes domains with the specified IDs from the Stalwart server."""

		if not ids:
			frappe.throw(title=_("No domain IDs provided"), msg=_("No domain IDs provided for deletion."))

		response = self.run(["delete", "Domain", "--ids", ",".join(ids)])

		if not response["success"]:
			frappe.throw(title=_("Failed to delete domains"), msg=response["output"] or response["error"])
