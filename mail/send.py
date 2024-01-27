import dkim
import frappe
import smtplib
from email.utils import formatdate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from frappe.utils.password import get_decrypted_password


def sendmail(email):
	server = frappe.get_cached_doc("FM Server", email.server)
	display_name = frappe.get_cached_value("FM Mailbox", email.sender, "display_name")
	dkim_selector = frappe.get_cached_value(
		"FM Domain", email.domain_name, "dkim_selector"
	)
	dkim_private_key = get_decrypted_password(
		"FM Domain", email.domain_name, "dkim_private_key"
	)

	message = MIMEMultipart("alternative")
	message["From"] = (
		"{0} <{1}>".format(display_name, email.sender) if display_name else email.sender
	)
	message["To"] = ", ".join(email.get_recipients())
	message["Subject"] = email.subject
	message["Date"] = formatdate()
	message["Message-ID"] = "<{0}@{1}>".format(email.name, server.name)

	if email.body:
		message.attach(MIMEText(email.body, "html"))

	headers = [b"To", b"From", b"Subject"]
	signature = dkim.sign(
		message=message.as_bytes(),
		domain=email.domain_name.encode(),
		selector=dkim_selector.encode(),
		privkey=dkim_private_key.encode(),
		include_headers=headers,
	)
	message["DKIM-Signature"] = signature[len("DKIM-Signature: ") :].decode()
	with smtplib.SMTP(server.host or server.name, server.port) as smtp_server:
		if server.use_tls:
			smtp_server.starttls()

		if server.username and server.password:
			smtp_server.login(server.username, server.get_password("password"))

		smtp_server.ehlo(email.domain_name)
		smtp_server.send_message(message)
