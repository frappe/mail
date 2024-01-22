import dkim
import frappe
import smtplib
from email.utils import formatdate
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def enqueue():
	email = frappe.qb.DocType("FM Outgoing Email")
	draft_emails = (
		frappe.qb.from_(email)
		.select(email.server, email.name)
		.where((email.status == "Draft"))
		.orderby(email.creation)
	).run(as_dict=True, as_iterator=True)

	queued_emails = {}
	for draft_email in draft_emails:
		queued_emails.setdefault(draft_email.server, []).append(draft_email.name)

	if not queued_emails:
		return

	for server, emails in queued_emails.items():
		frappe.enqueue(
			sendmail,
			queue="long",
			job_name=f"sendmail-{server}",
			server=server,
			emails=emails,
		)


def sendmail(server: str, emails: list):
	email = frappe.qb.DocType("FM Outgoing Email")
	frappe.qb.update(email).set(email.status, "Queued").where(
		email.name.isin(emails)
	).run()
	frappe.db.commit()

	outgoing_server = frappe.get_cached_doc("FM Server", server)
	for email in emails:
		email = frappe.get_doc("FM Outgoing Email", email, for_update=True)
		fm_domain = frappe.get_cached_doc("FM Domain", email.domain_name)
		display_name = frappe.get_cached_value("FM Mailbox", email.sender, "display_name")

		message = MIMEMultipart("alternative")
		message["From"] = (
			"{0} <{1}>".format(display_name, email.sender) if display_name else email.sender
		)
		message["To"] = ", ".join(email.get_recipients())
		message["Subject"] = email.subject
		message["Date"] = formatdate()
		message["Message-ID"] = "<{0}@{1}>".format(email.name, outgoing_server.name)

		if email.body:
			message.attach(MIMEText(email.body, "html"))

		headers = [b"To", b"From", b"Subject"]
		signature = dkim.sign(
			message=message.as_bytes(),
			domain=fm_domain.domain_name.encode(),
			selector=fm_domain.dkim_selector.encode(),
			privkey=fm_domain.get_password("dkim_private_key").encode(),
			include_headers=headers,
		)
		message["DKIM-Signature"] = signature[len("DKIM-Signature: ") :].decode()

		try:
			with smtplib.SMTP(outgoing_server.name, outgoing_server.port) as server:
				if outgoing_server.use_tls:
					server.starttls()

				if outgoing_server.username and outgoing_server.password:
					server.login(outgoing_server.username, outgoing_server.get_password("password"))

				server.ehlo(email.domain_name)
				server.send_message(message)

				email.update_status(status="Sent")
		except Exception:
			error_log = frappe.log_error(title="FM Outgoing Email")
			email.update_status(status="Failed", error_log=error_log.name)
