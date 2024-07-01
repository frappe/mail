import frappe
from frappe.translate import get_all_translations
from frappe.utils import is_html
import re
from bs4 import BeautifulSoup

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
	mails = frappe.get_all("Incoming Mail", {
		"receiver": frappe.session.user,
		"docstatus": 1
	}, ["name", "receiver", "sender", "body_html", "body_plain", "display_name", "subject"],
	limit=50,
	start=start,
	order_by="created_at desc")

	for mail in mails:
		mail.latest_content = get_latest_content(mail.body_html, mail.body_plain)
		mail.snippet = get_snippet(mail.latest_content) if mail.latest_content else ""

	return mails

@frappe.whitelist()
def get_outgoing_mails(start=0):
	mails = frappe.get_all("Outgoing Mail", {
		"sender": frappe.session.user,
		"docstatus": 1
	}, ["name", "subject", "sender", "body_html", "body_plain"],
	limit=50,
	start=start,
	order_by="created_at desc")

	for mail in mails:
		mail.latest_content = get_latest_content(mail.body_html, mail.body_plain)
		mail.snippet = get_snippet(mail.latest_content) if mail.latest_content else ""

	return mails

def get_latest_content(html, plain):
	content = html if html else plain
	if content is None:
		return ''
	
	# Check if the content is HTML
	if is_html(content):
		soup = BeautifulSoup(content, 'html.parser')	# Parse the content with BeautifulSoup
		div = soup.find('div', {'dir': 'ltr'})	# Find the first div with dir="ltr"
		if div is None:
			return content	# Return the content if no div is found
		return div.get_text(strip=True)	# Otherwise, return the text of the div
	else:
		lines = content.split('\n')	# If the content is plain text, split it into lines
		return '\n'.join(lines[:2])	# Return the first two lines joined by a newline character
	
def get_snippet(content):
	if is_html(content):
		soup = BeautifulSoup(content, 'html.parser')
		email_body = soup.find(class_='email-body')
		if email_body:
			words = email_body.get_text(strip=True).split()
		else:
			words = soup.get_text(strip=True).split()
		return ' '.join(words[:50])
	else:
		return ' '.join(content.split()[:50])
	

@frappe.whitelist()
def get_mail_details(name, type):
	fields = ["name", "subject", "body_html", "body_plain", "sender"]
	if type == "Incoming Mail":
		fields += ["receiver", "display_name"]
	
	mail = frappe.db.get_value(type, name, fields, as_dict=1)
	
	if not mail.display_name:
		mail.display_name = frappe.db.get_value("User", mail.sender, "full_name")

	mail.user_image = frappe.db.get_value("User", mail.sender, "user_image")
	mail.latest_content = get_latest_content(mail.body_html, mail.body_plain)

	if mail.body_html:
		mail.body_html = extract_email_body(mail.body_html)
	return mail

def extract_email_body(html):
	soup = BeautifulSoup(html, 'html.parser')
	email_body = soup.find("table", class_='email-body')
	if email_body:
		return email_body.find('div').prettify()
	return html