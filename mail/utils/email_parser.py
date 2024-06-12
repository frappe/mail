import re
from email.utils import parseaddr
from email.header import decode_header
from typing import Optional, TYPE_CHECKING
from mail.utils import parsedate_to_datetime
from frappe.utils import cint, get_datetime_str
from frappe.utils.file_manager import save_file

if TYPE_CHECKING:
	from email.message import Message


class EmailParser:
	def __init__(self, message: str) -> None:
		self.message = self.get_parsed_message(message)
		self.content_id_and_file_url_map = {}

	@staticmethod
	def get_parsed_message(message: str) -> "Message":
		"""Returns parsed email message object from string."""

		from email import message_from_string

		return message_from_string(message)

	def get_subject(self) -> str:
		"""Returns the decoded subject of the email."""

		return decode_header(self.message["Subject"])[0][0]

	def get_sender(self) -> tuple[str, str]:
		"""Returns the display name and email of the sender."""

		return parseaddr(self.message["From"])

	def get_header(self, header: str) -> str:
		"""Returns the value of the header."""

		return self.message[header]

	def update_header(self, header: str, value: str) -> None:
		"""Updates the value of the header."""

		del self.message[header]
		self.message[header] = value

	def get_date(self) -> str:
		"""Returns the date of the email."""

		return get_datetime_str(parsedate_to_datetime(self.message["Date"]))

	def get_size(self) -> int:
		"""Returns the size of the email."""

		return len(self.message.as_bytes())

	def get_recipients(self, types: Optional[str | list] = None) -> list[dict]:
		"""Returns the list of recipients of the email."""

		if not types:
			types = ["To", "Cc", "Bcc"]
		elif isinstance(types, str):
			types = [types]

		recipients = []
		for type in types:
			if addresses := self.message.get(type):
				for address in addresses.split(","):
					display_name, email = parseaddr(address)
					if email:
						recipients.append({"type": type, "email": email, "display_name": display_name})

		return recipients

	def save_attachments(
		self, doctype: str, docname: str, is_private: bool = True
	) -> None:
		"""Saves the attachments of the email."""

		def save_attachment(
			filename: str, content: bytes, doctype: str, docnamme: str, is_private: bool
		) -> dict:
			"""Saves the attachment as a file."""

			kwargs = {
				"fname": filename,
				"content": content,
				"df": "file",
				"dt": doctype,
				"dn": docnamme,
				"is_private": cint(is_private),
			}
			file = save_file(**kwargs)

			return {
				"name": file.name,
				"file_name": file.file_name,
				"file_url": file.file_url,
				"is_private": file.is_private,
			}

		for part in self.message.walk():
			filename = part.get_filename()
			disposition = part.get("Content-Disposition")

			if disposition and filename:
				disposition = disposition.lower()

				if disposition.startswith("inline"):
					if content_id := re.sub(r"[<>]", "", part.get("Content-ID", "")):
						if payload := part.get_payload(decode=True):
							if part.get_content_charset():
								payload = payload.decode(part.get_content_charset(), "ignore")

							file = save_attachment(filename, payload, doctype, docname, is_private)
							self.content_id_and_file_url_map[content_id] = file["file_url"]

				elif disposition.startswith("attachment"):
					save_attachment(
						filename, part.get_payload(decode=True), doctype, docname, is_private
					)

	def get_body(self) -> tuple[str, str]:
		"""Returns the HTML and plain text body of the email."""

		body_html, body_plain = "", ""

		for part in self.message.walk():
			content_type = part.get_content_type()

			if content_type == "text/html":
				body_html += part.get_payload(decode=True).decode(
					part.get_content_charset(), "ignore"
				)

			elif content_type == "text/plain":
				body_plain += part.get_payload(decode=True).decode(
					part.get_content_charset() or "utf-8", "ignore"
				)

		if self.content_id_and_file_url_map:
			for content_id, file_url in self.content_id_and_file_url_map.items():
				body_html = body_html.replace("cid:" + content_id, file_url)
				body_plain = body_plain.replace("cid:" + content_id, file_url)

		return body_html, body_plain

	def get_authentication_results(self) -> dict[str, int | str]:
		"""Returns the authentication results of the email."""

		result = {}
		checks = ["spf", "dkim", "dmarc"]

		for check in checks:
			result[check] = 0
			result[f"{check}_description"] = "Header not found."

		if headers := self.message.get_all("Authentication-Results"):
			if len(headers) == 1:
				headers = headers[0].split(";")

			for header in headers:
				header = header.replace("\n", "").replace("\t", "")
				header_lower = header.lower()

				for check in checks:
					if f"{check}=" in header_lower:
						result[check] = 1 if f"{check}=pass" in header_lower else 0
						result[f"{check}_description"] = header
						break

		return result
