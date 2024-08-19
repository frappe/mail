# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class MailFolder(Document):
	def validate(self) -> None:
		self.set_inbound_outbound()

	def set_inbound_outbound(self) -> None:
		inbound_outbound_map = {
			"Drafts": {"inbound": 0, "outbound": 1},
			"Sent": {"inbound": 0, "outbound": 1},
			"Inbox": {"inbound": 1, "outbound": 0},
			"Spam": {"inbound": 1, "outbound": 0},
			"Trash": {"inbound": 1, "outbound": 1},
		}

		self.inbound = inbound_outbound_map[self.folder_type]["inbound"]
		self.outbound = inbound_outbound_map[self.folder_type]["outbound"]
