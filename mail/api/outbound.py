import json
import frappe
from frappe.utils import cint
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
		to = mail.get("to")
		cc = mail.get("cc")
		bcc = mail.get("bcc")
		sender = mail.get("from")
		subject = mail.get("subject")
		raw_html = mail.get("html")
		custom_headers = mail.get("headers")
		attachments = mail.get("attachments")
		track = cint(mail.get("track") or mail.get("enable_tracking"))

		if mail.get("mode") == "individual" and isinstance(to, list) and len(to) > 1:
			for recipient in to:
				doc = create_outgoing_mail(
					sender,
					subject,
					recipient,
					cc,
					bcc,
					raw_html,
					track,
					attachments,
					custom_headers,
					via_api=1,
					send_in_batch=1,
				)
				docs.append(doc.name)
		else:
			doc = create_outgoing_mail(
				sender,
				subject,
				to,
				cc,
				bcc,
				raw_html,
				track,
				attachments,
				custom_headers,
				via_api=1,
				send_in_batch=send_in_batch,
			)
			docs.append(doc.name)

	frappe.get_doc(
		"Scheduled Job Type",
		{"method": "mail.mail.doctype.outgoing_mail.outgoing_mail.transfer_mails"},
	).enqueue(force=True)

	return docs
