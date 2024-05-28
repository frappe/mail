import json
import frappe
from mail.mail.doctype.outgoing_mail.outgoing_mail import create_outgoing_mail


@frappe.whitelist(methods=["POST"])
def send() -> list[str]:
	"""Send Mail(s)."""

	send_in_batch = 1
	mails = json.loads(frappe.request.data.decode())

	if isinstance(mails, dict):
		mails = [mails]
		send_in_batch = 0

	docs = []
	for mail in mails:
		sender = mail.get("from") or mail.get("sender")
		subject = mail.get("subject")
		raw_html = mail.get("html") or mail.get("raw_html")
		recipients = mail.get("to") or mail.get("recipient") or mail.get("recipients")
		custom_headers = (
			mail.get("header") or mail.get("headers") or mail.get("custom_headers")
		)

		if (
			mail.get("mode") == "individual"
			and isinstance(recipients, list)
			and len(recipients) > 1
		):
			for recipient in recipients:
				doc = create_outgoing_mail(
					sender, subject, recipient, raw_html, custom_headers, send_in_batch=1
				)
				docs.append(doc.name)
		else:
			doc = create_outgoing_mail(
				sender, subject, recipients, raw_html, custom_headers, send_in_batch=send_in_batch
			)
			docs.append(doc.name)

	frappe.get_doc(
		"Scheduled Job Type",
		{"method": "mail.mail.doctype.outgoing_mail.outgoing_mail.transfer_mails"},
	).enqueue()

	return docs
