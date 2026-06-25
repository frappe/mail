import frappe
from frappe.model.document import bulk_insert


def execute() -> None:
	"""Merge the legacy "Blocked Email Address" and "Junk Email Address" doctypes into the unified
	"Screened Email Address" doctype, then drop the old doctypes.

	A blocked address becomes a Reject rule (discard) and a junked address becomes a Spam rule (file
	into Junk). All three doctypes are keyed on the shared `account_id` (the legacy ones were
	backfilled earlier in this migration), and a sender has at most one rule, so a Reject always
	supersedes a Spam for the same (account_id, email).

	Inserted via `bulk_insert` (no per-document hooks), so the sieve scripts are not regenerated here:
	the existing server-side sieve blocks already reflect the same addresses and actions, and the new
	unified block names supersede the legacy ones the next time a screening change is made.
	"""

	if not frappe.db.exists("DocType", "Screened Email Address"):
		return

	seen: set[tuple[str, str]] = set()
	docs = []

	def add(account_id: str, email: str, action: str, creation) -> None:
		if not email or not account_id:
			return

		key = (account_id, email)
		if key in seen:  # Reject (inserted first) supersedes Spam for the same address.
			return
		seen.add(key)

		doc = frappe.get_doc(
			{
				"doctype": "Screened Email Address",
				"account_id": account_id,
				"email": email,
				"action": action,
			}
		)
		doc.set_new_name()
		if creation:
			doc.creation = creation
		docs.append(doc)

	# Reject rules first so they win over a Spam rule for the same address.
	if frappe.db.table_exists("Blocked Email Address"):
		for row in frappe.get_all(
			"Blocked Email Address",
			fields=["account_id", "email", "creation"],
			order_by="creation asc",
		):
			add(row.account_id, row.email, "Reject", row.creation)

	if frappe.db.table_exists("Junk Email Address"):
		for row in frappe.get_all(
			"Junk Email Address",
			fields=["account_id", "email", "creation"],
			order_by="creation asc",
		):
			add(row.account_id, row.email, "Spam", row.creation)

	if docs:
		bulk_insert("Screened Email Address", docs, ignore_duplicates=True)

	# The data now lives in Screened Email Address; drop the now-redundant legacy doctypes. delete_doc
	# removes the DocType definition but leaves the table behind, so drop it explicitly too.
	for doctype in ("Blocked Email Address", "Junk Email Address"):
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, ignore_missing=True, force=True)
		frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{doctype}`")
