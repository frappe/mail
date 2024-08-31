import re
import frappe
from bs4 import BeautifulSoup
from frappe.utils import is_html
from frappe.translate import get_all_translations


@frappe.whitelist(allow_guest=True)
def get_branding():
	"""Get branding details."""
	return {
		"brand_name": frappe.db.get_single_value("Website Settings", "app_name"),
		"brand_html": frappe.db.get_single_value("Website Settings", "brand_html"),
		"favicon": frappe.db.get_single_value("Website Settings", "favicon"),
	}


@frappe.whitelist(allow_guest=True)
def get_user_info():
	if frappe.session.user == "Guest":
		return None

	user = frappe.db.get_value(
		"User",
		frappe.session.user,
		["name", "email", "enabled", "user_image", "full_name", "user_type", "username"],
		as_dict=1,
	)
	user["roles"] = frappe.get_roles(user.name)
	user.mail_user = "Mailbox User" in user.roles
	user.domain_owner = "Domain Owner" in user.roles
	user.postmaster = "Postmaster" in user.roles
	return user


@frappe.whitelist(allow_guest=True)
def get_translations():
	if frappe.session.user != "Guest":
		language = frappe.db.get_value("User", frappe.session.user, "language")
	else:
		language = frappe.db.get_single_value("System Settings", "language")
	return get_all_translations(language)


@frappe.whitelist()
def get_incoming_mails(start=0):
	mails = frappe.get_all(
		"Incoming Mail",
		{"receiver": frappe.session.user, "docstatus": 1},
		["name", "sender", "body_html", "body_plain", "display_name", "subject", "creation"],
		limit=50,
		start=start,
		order_by="created_at desc",
	)

	for mail in mails:
		mail.latest_content = get_latest_content(mail.body_html, mail.body_plain)
		mail.snippet = get_snippet(mail.latest_content) if mail.latest_content else ""

	return mails


@frappe.whitelist()
def get_outgoing_mails(start=0):
	mails = frappe.get_all(
		"Outgoing Mail",
		{
			"sender": frappe.session.user,
			"docstatus": 1,
			"status": "Sent",
		},
		["name", "subject", "sender", "body_html", "body_plain", "creation", "display_name"],
		limit=50,
		start=start,
		order_by="created_at desc",
	)

	for mail in mails:
		mail.latest_content = get_latest_content(mail.body_html, mail.body_plain)
		mail.snippet = get_snippet(mail.latest_content) if mail.latest_content else ""

	return mails


def get_latest_content(html, plain):
	content = html if html else plain
	if content is None:
		return ""

	if is_html(content):
		soup = BeautifulSoup(content, "html.parser")
		blockquote = soup.find("blockquote")
		if blockquote:
			blockquote.extract()
		return soup.get_text(strip=True)

	return content


def get_snippet(content):
	content = re.sub(
		r"(?<=[.,])(?=[^\s])", r" ", content
	)  # add space after . and , if not followed by a space
	return " ".join(content.split()[:50])


@frappe.whitelist()
def get_mail_thread(name, mail_type):
	# Mail has reply to
	# Mail has replica that has reply to
	# Its the first mail of the thread so fetch emails to which this is the reply to

	mail = get_mail_details(name, mail_type)
	mail.mail_type = mail_type

	original_replica = find_replica(mail, mail_type)

	thread = []
	visited = set()

	def get_thread(mail, thread):
		thread.append(mail)
		if mail.name in visited:
			return
		visited.add(mail.name)

		if mail.in_reply_to_mail_name:
			reply_mail = get_mail_details(mail.in_reply_to_mail_name, mail.in_reply_to_mail_type)
			get_thread(reply_mail, thread)
		else:
			replica = find_replica(mail, mail.mail_type)
			if replica and replica != name:
				replica_type = reverse_type(mail.mail_type)
				replica_mail = get_mail_details(replica, replica_type)
				replica_mail.mail_type = replica_type
				get_thread(replica_mail, thread)
			else:
				replies = []
				replies += gather_thread_replies(name)
				replies += gather_thread_replies(original_replica)

				for reply in replies:
					if reply.name not in visited:
						get_thread(reply, thread)

	get_thread(mail, thread)
	thread = remove_duplicates_and_sort(thread)
	return thread


def reverse_type(mail_type):
	return "Incoming Mail" if mail_type == "Outgoing Mail" else "Outgoing Mail"


def gather_thread_replies(mail_name):
	thread = []
	thread += get_thread_from_replies("Outgoing Mail", mail_name)
	thread += get_thread_from_replies("Incoming Mail", mail_name)
	return thread


def get_thread_from_replies(mail_type, mail_name):
	replies = []
	emails = frappe.get_all(mail_type, {"in_reply_to_mail_name": mail_name}, pluck="name")
	for email in emails:
		reply = get_mail_details(email, mail_type)
		reply.mail_type = mail_type
		replies.append(reply)

	return replies


def find_replica(mail, mail_type):
	replica_type = "Incoming Mail" if mail_type == "Outgoing Mail" else "Outgoing Mail"
	return frappe.db.exists(replica_type, {"message_id": mail.message_id})


def remove_duplicates_and_sort(thread):
	seen = set()
	thread = [x for x in thread if x["name"] not in seen and not seen.add(x["name"])]
	thread = [
		x for x in thread if x["message_id"] not in seen and not seen.add(x["message_id"])
	]
	thread.sort(key=lambda x: x.creation)
	return thread


def get_mail_details(name, type):
	fields = [
		"name",
		"subject",
		"body_html",
		"body_plain",
		"sender",
		"display_name",
		"creation",
		"message_id",
		"in_reply_to_mail_name",
		"in_reply_to_mail_type",
	]

	mail = frappe.db.get_value(type, name, fields, as_dict=1)
	if not mail.display_name:
		mail.display_name = frappe.db.get_value("User", mail.sender, "full_name")

	mail.user_image = frappe.db.get_value("User", mail.sender, "user_image")
	mail.latest_content = get_latest_content(mail.body_html, mail.body_plain)
	mail.to = get_recipients(name, type, "To")
	mail.cc = get_recipients(name, type, "Cc")
	mail.bcc = get_recipients(name, type, "Bcc")
	mail.body_html = extract_email_body(mail.body_html)
	mail.mail_type = type
	return mail


def extract_email_body(html):
	if not html:
		return
	soup = BeautifulSoup(html, "html.parser")
	email_body = soup.find("table", class_="email-body")
	if email_body:
		return email_body.find("div").prettify()
	return html


def get_recipients(name, type, recipient_type):
	recipients = frappe.get_all(
		"Mail Recipient",
		{"parent": name, "parenttype": type, "type": recipient_type},
		["email", "display_name", "type"],
	)

	for recipient in recipients:
		if not recipient.display_name:
			recipient.display_name = frappe.db.get_value("User", recipient.email, "full_name")

	return recipients


@frappe.whitelist()
def get_mail_contacts(txt=None):
	filters = {"user": frappe.session.user}
	if txt:
		filters["email"] = ["like", f"%{txt}%"]

	contacts = frappe.get_all("Mail Contact", filters=filters, fields=["email"])

	for contact in contacts:
		details = frappe.db.get_value(
			"User", {"email": contact.email}, ["user_image", "full_name", "email"], as_dict=1
		)
		if details:
			contact.update(details)

	return contacts
