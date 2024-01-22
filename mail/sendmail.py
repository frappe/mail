import frappe


@frappe.whitelist(allow_guest=True, methods=["POST"])
def enqueue(sender: str, recipients: str, subject: str = None, body: str = None):
	doc = frappe.new_doc("FM Outgoing Email")
	doc.sender = sender

	recipients = recipients.split(",")
	doc.add_recipients(recipients)

	doc.subject = subject
	doc.body = body

	doc.insert(ignore_permissions=True)

	return doc.name
