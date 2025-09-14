import base64
import gzip
import hashlib
import os
import random
import re
import secrets
import string
import tarfile
import zipfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from io import BytesIO
from typing import Any, Literal

import bcrypt
import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.types.filter import FilterTuple
from frappe.utils import get_bench_path
from frappe.utils.caching import redis_cache


def hash_password(password: str) -> str:
	"""Generate a bcrypt hash for a given password."""

	salt = bcrypt.gensalt()
	hashed = bcrypt.hashpw(password.encode(), salt)
	return hashed.decode()


def verify_password(password: str, hashed_password: str) -> bool:
	"""Verify if a password matches the stored bcrypt hash."""

	return bcrypt.checkpw(password.encode(), hashed_password.encode())


def generate_random_phrase() -> str:
	"""Generate a random passphrase consisting of 5 words."""

	return " ".join(["".join(random.choices(string.ascii_lowercase, k=l)) for l in (5, 4, 4, 4, 3)])


def reformat_pbkdf2_hash(passlib_hash: str, dklen: int | None = None) -> str:
	"""Normalize a PBKDF2 hash into a consistent format."""

	prefix, iterations, salt_mod, hash_mod = passlib_hash.strip("$").split("$")
	iterations = int(iterations)

	def b64decode_mod(s: str) -> bytes:
		s = s.replace(".", "+").replace("-", "/")
		pad_len = (-len(s)) % 4
		return base64.b64decode(s + ("=" * pad_len))

	def b64encode_std(b: bytes) -> str:
		return base64.b64encode(b).decode().rstrip("=")

	salt_bytes = b64decode_mod(salt_mod)
	salt_b64 = b64encode_std(salt_bytes)

	hash_bytes = b64decode_mod(hash_mod)
	if dklen is None:
		dklen = len(hash_bytes)
	hash_clean = b64encode_std(hash_bytes)

	formatted_hash = f"${prefix}$i={iterations},l={dklen}${salt_b64}${hash_clean}"
	return formatted_hash


@contextmanager
def user_context(user: str) -> Generator[None, None, None]:
	"""Context manager to temporarily switch the user context."""

	session_user = frappe.session.user
	session_data = frappe.session.data.copy()

	if session_user == user:
		yield
		return

	try:
		frappe.set_user(user)
		yield
	finally:
		frappe.set_user(session_user)
		frappe.session.data = session_data


def encode_image_to_base64(image_path: str) -> str:
	"""Encodes an image to a base64 string with line breaks every 76 characters."""

	image_path = os.path.abspath(image_path)
	with open(image_path, "rb") as image:
		image_base64 = base64.b64encode(image.read()).decode("utf-8")

	chunk_size = 76
	parts = [image_base64[i : i + chunk_size] for i in range(0, len(image_base64), chunk_size)]
	return "\n".join(parts)


def get_base64_image_data_uri(image_path: str) -> str:
	"""Generates a base64 data URI for an image."""

	image_base64 = encode_image_to_base64(image_path)
	image_format = image_path.split(".")[-1]
	return f"data:image/{image_format};base64,{image_base64}"


def generate_otp(length=5) -> int:
	"""Generates a random OTP."""

	lower_bound = 10 ** (length - 1)
	upper_bound = 10**length
	return int.from_bytes(os.urandom(length), byteorder="big") % (upper_bound - lower_bound) + lower_bound


def generate_secret(length: int = 32) -> str:
	"""Generates a random secret key."""

	characters = string.ascii_letters + string.digits
	return "".join(secrets.choice(characters) for _ in range(length))


def load_compressed_file(file_path: str | None = None, file_data: bytes | None = None) -> str:
	"""Load content from a compressed file (ZIP or GZIP) or a bytes object."""

	def extract_zip_content(zip_source) -> str | None:
		with zipfile.ZipFile(zip_source, "r") as zip_file:
			file_name = zip_file.namelist()[0]
			with zip_file.open(file_name) as file:
				return file.read().decode()

	def extract_gzip_content(gzip_source) -> str | None:
		with gzip.open(gzip_source, "rt") as gz_file:
			return gz_file.read()

	if not file_path and not file_data:
		frappe.throw(_("Either file path or file data is required."))

	if file_path:
		if zipfile.is_zipfile(file_path):
			return extract_zip_content(file_path)
		return extract_gzip_content(file_path)

	if isinstance(file_data, str):
		file_data = file_data.encode()

	try:
		return extract_zip_content(BytesIO(file_data))
	except zipfile.BadZipFile:
		pass

	try:
		return extract_gzip_content(BytesIO(file_data))
	except OSError:
		pass

	frappe.throw(_("Failed to load content from the compressed file."))


def extract_compressed_file(file_path: str, destination: str) -> None:
	"""Extract a .zip, .tar.gz, or .tgz archive to the specified destination directory."""

	if not os.path.exists(file_path):
		frappe.throw(_("File not found: {0}").format(file_path))

	if file_path.endswith(".zip"):
		with zipfile.ZipFile(file_path, "r") as archive:
			archive.extractall(destination)

	elif file_path.endswith((".tar.gz", ".tgz")):
		with tarfile.open(file_path, "r:gz") as archive:
			archive.extractall(destination)

	else:
		frappe.throw(_("Unsupported file format: {0}").format(file_path))


def get_mbox_files(base_dir: str) -> list[str]:
	"""Recursively find and return all .mbox files under the given directory."""

	mbox_files = [
		os.path.join(root, filename)
		for root, _, files in os.walk(base_dir)
		for filename in files
		if filename.endswith(".mbox")
	]
	return mbox_files


def compress_directory(source_dir: str, output_path: str) -> None:
	"""Compress a directory into .zip, .tgz, or .tar.gz format based on output file extension."""

	if output_path.endswith(".zip"):
		with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
			for root, _dirs, files in os.walk(source_dir):
				for file in files:
					file_path = os.path.join(root, file)
					relative_path = os.path.relpath(file_path, source_dir)
					zip_file.write(file_path, relative_path)

	elif output_path.endswith(".tgz") or output_path.endswith(".tar.gz"):
		with tarfile.open(output_path, "w:gz") as tar_file:
			tar_file.add(source_dir, arcname=".")

	else:
		frappe.throw(_("Unsupported output file format. Supported formats are .zip, .tgz, and .tar.gz."))


def enqueue_job(
	method: str | Callable, job_id: str | None = None, deduplicate: bool = False, **kwargs
) -> None:
	"""Enqueues a background job."""

	if deduplicate and not job_id:
		job_id = method.split(".")[-1] if isinstance(method, str) else method.__name__

	frappe.enqueue(method, job_id=job_id, deduplicate=deduplicate, **kwargs)


def rename_keys(data: dict, rename_map: dict) -> dict:
	"""
	Rename keys in a dictionary based on a given mapping.

	:param data: The original dictionary.
	:param rename_map: A dictionary mapping old keys to new keys.
	:return: A new dictionary with renamed keys.
	"""

	return {rename_map.get(k, k): v for k, v in data.items()}


def convert_html_to_text(html: str) -> str:
	"""Returns plain text from HTML content."""

	if not html:
		return ""

	soup = BeautifulSoup(html, "html.parser")
	text = soup.get_text(separator=" ")
	return re.sub(r"\s+", " ", text).strip()


def extract_filter_values(filters: list, conditions: list[dict]) -> tuple:
	"""Extracts specific filter values from a filter list based on given conditions."""

	values = {list(condition.keys())[0]: None for condition in conditions}
	condition_map = {list(condition.keys())[0]: list(condition.values())[0] for condition in conditions}

	for f in filters:
		key, operator, value = f[1], f[2], f[3]
		if key in condition_map and operator == condition_map[key]:
			values[key] = value.replace("%", "") if operator == "like" else value

	return tuple(values[key] for key in values)


def parse_filters(filters: list | None) -> dict:
	"""Parses a list of filters into a dictionary of fieldname-value pairs for equality conditions."""

	if not filters:
		return {}

	result = {}
	for f in filters:
		if isinstance(f, list):
			f = FilterTuple(f)

		if f.operator == "=":
			result[f.fieldname] = f.value

	return result


def sanitize_cli_output(text: str) -> str:
	"""Remove ANSI escape sequences and control characters from text."""

	if text:
		ansi_escape = re.compile(r"(?:\x1B[@-Z\\-_]|\x1B\[[0-?]*[ -/]*[@-~])")

		# Remove ANSI escape codes
		text = ansi_escape.sub("", text)

		# Remove other control characters except newline/tab
		text = re.sub(r"[^\x20-\x7E\n\t]", "", text)

		return text.strip()

	return text


@frappe.whitelist()
@redis_cache(ttl=3600)
def check_deliverability(email: str) -> bool:
	"""Wrapper function of `utils.validation.validate_email_address` for caching."""

	from mail.utils.validation import validate_email_address

	return validate_email_address(email, check_mx=True, verify=True, smtp_timeout=10)


def remove_subaddressing(email: str) -> str:
	"""Removes subaddressing from an email address.

	Example:
	    input: "user+filter@example.com"
	    output: "user@example.com"
	"""
	match = re.match(r"([^+]+)(?:\+[^@]*)?(@.+)", email)
	return f"{match.group(1)}{match.group(2)}" if match else email


def normalize_email(email: str) -> str:
	"""Normalize email by removing dots before the @."""

	local, domain = email.split("@", 1)
	normalized_local = re.sub(r"\.", "", local)
	return f"{normalized_local}@{domain}"


def flatten_dict(d, parent_key="", sep=".") -> dict:
	"""Recursively flattens a nested dictionary into dot notation."""

	items = {}
	for k, v in d.items():
		new_key = f"{parent_key}{sep}{k}" if parent_key else k
		if isinstance(v, dict):
			items.update(flatten_dict(v, new_key, sep))
		else:
			items[new_key] = v
	return items


def password_or_none(doc, field: str) -> str | None:
	"""Returns the password if the field is set, otherwise returns None."""

	return doc.get_password(field) if doc.get(field) else None


def batch_dict(d: dict[str, Any], batch_size: int) -> list[dict[str, Any]]:
	"""Splits a dictionary into smaller dictionaries of a specified batch size."""

	keys = list(d.keys())
	return [{k: d[k] for k in keys[i : i + batch_size]} for i in range(0, len(keys), batch_size)]


def get_dotted_path(func: Callable) -> str:
	"""Returns the dotted path of a function."""

	return f"{func.__module__}.{func.__qualname__}"


def generate_uuid_style_hash(input_str: str) -> str:
	"""Generates a UUID-style hash from the input string."""

	hash = hashlib.md5(input_str.encode()).hexdigest()
	return f"{hash[:8]}-{hash[8:12]}-{hash[12:16]}-{hash[16:20]}-{hash[20:]}"


def get_mail_app_path() -> str:
	"""Returns the path to the Mail app directory."""

	return os.path.join(get_bench_path(), "apps/mail")


def get_messages_directory() -> str:
	"""Returns the path to the messages directory for the current site."""

	directory = os.path.join(get_bench_path(), "sites", frappe.local.site, "raw_messages")
	os.makedirs(directory, exist_ok=True)
	return directory


def get_import_directory() -> str:
	"""Returns the path to the import directory for the current site."""

	directory = os.path.join(get_bench_path(), "sites", frappe.local.site, "imports")
	os.makedirs(directory, exist_ok=True)
	return directory


def get_export_directory() -> str:
	"""Returns the path to the export directory for the current site."""

	directory = os.path.join(get_bench_path(), "sites", frappe.local.site, "exports")
	os.makedirs(directory, exist_ok=True)
	return directory


def get_stalwart_cli_path() -> str:
	"""Returns the path to the Stalwart CLI tool, raising an error if not found."""

	cli_path = os.path.join(get_mail_app_path(), "stalwart-cli")
	if not os.path.exists(cli_path):
		relpath = os.path.relpath(cli_path, get_bench_path())
		frappe.throw(_("Stalwart CLI not found at {0}.").format(relpath))

	return cli_path


def get_dkim_host(domain_name: str, type: Literal["rsa", "ed25519"]) -> str:
	"""
	Returns DKIM host.
	e.g. example-com-r for RSA and example-com-e for Ed25519.
	"""

	return f"{domain_name.replace('.', '-')}-{type[0]}"


def get_dkim_selector(key_type: Literal["rsa", "ed25519"]) -> str:
	"""
	Returns DKIM selector.
	e.g. frappemail-r for RSA and frappemail-e for Ed25519.
	"""

	return f"frappemail-{key_type[0]}"
