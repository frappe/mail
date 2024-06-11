import json
import frappe
from frappe.utils import cint
from email.utils import parseaddr
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
		sender = parseaddr(mail.get("from"))[1]
		subject = mail.get("subject")
		to = mail.get("to")
		cc = mail.get("cc")
		bcc = mail.get("bcc")
		raw_html = mail.get("html")
		raw_message = mail.get("message")
		reply_to = mail.get("reply-to") or mail.get("reply_to")
		track = cint(mail.get("track") or mail.get("enable_tracking"))
		attachments = mail.get("attachments")
		custom_headers = mail.get("headers")

		if mail.get("mode") == "individual" and isinstance(to, list) and len(to) > 1:
			for recipient in to:
				doc = create_outgoing_mail(
					sender,
					subject,
					recipient,
					cc,
					bcc,
					raw_html,
					raw_message,
					reply_to,
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
				raw_message,
				reply_to,
				track,
				attachments,
				custom_headers,
				via_api=1,
				send_in_batch=send_in_batch,
			)
			docs.append(doc.name)

	return docs
