# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from uuid import uuid7

from frappe.model.document import Document

from mail.jmap import parse_account


class AccountState(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def before_insert(self) -> None:
		user, _account_id = parse_account(self.account)
		self.user = user
