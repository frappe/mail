# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class JMAPPushVerificationQueue(Document):
	def validate(self):
		self.validate_status()

	def validate_status(self) -> None:
		"""Set status to 'Pending' if not set"""

		if not self.status:
			self.status = "Pending"

	def after_insert(self) -> None:
		if self.status == "Pending":
			frappe.enqueue_doc(self.doctype, self.name, "process", queue="short", enqueue_after_commit=True)

	@frappe.whitelist()
	def process(self) -> None:
		"""Process the JMAP Push Verification Queue."""

		kwargs = {}
		subscription_name = frappe.db.get_value(
			"Push Subscription",
			{"account": self.account, "subscription_id": self.subscription_id},
			"name",
		)

		if subscription_name:
			subscription = frappe.get_doc("Push Subscription", subscription_name)
			subscription._verify(self.get_password("verification_code"))
			kwargs["status"] = "Verified"
		else:
			kwargs["status"] = "Failed"

		self._db_set(**kwargs)

	@frappe.whitelist()
	def retry(self) -> None:
		"""Retry the verification process."""

		if self.status != "Failed":
			frappe.throw(_("Only failed verifications can be retried."))

		self._db_set(status="Pending")
		frappe.enqueue_doc(self.doctype, self.name, "process", queue="short", enqueue_after_commit=True)

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, notify=notify, commit=commit)


def process_verifications() -> None:
	"""Called by the scheduler to process pending JMAP Push Verification Queue entries."""

	for x in frappe.db.get_all("JMAP Push Verification Queue", filters={"status": "Pending"}, pluck="name"):
		frappe.get_doc("JMAP Push Verification Queue", x).process()
