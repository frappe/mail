# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

from mail.utils import convert_html_to_text


class MailSignature(Document):
	def validate(self) -> None:
		if self.html_body:
			self.text_body = convert_html_to_text(self.html_body)
