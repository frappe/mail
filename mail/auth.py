import posixpath
from urllib.parse import unquote

import frappe
from frappe import _

ALLOWED_PATHS = [
	"/api/method/frappe.core.doctype.communication.email.mark_email_as_seen",
	"/api/method/frappe.realtime.get_user_info",
	"/api/method/frappe.realtime.can_subscribe_doc",
	"/api/method/frappe.realtime.can_subscribe_doctype",
	"/api/method/frappe.realtime.has_permission",
	"/api/method/frappe.www.login.login_via_frappe",
	"/api/method/frappe.integrations.oauth2.authorize",
	"/api/method/frappe.integrations.oauth2.approve",
	"/api/method/frappe.integrations.oauth2.get_token",
	"/api/method/frappe.integrations.oauth2.openid_profile",
	"/api/method/frappe.integrations.oauth2_logins.login_via_frappe",
	"/api/method/frappe.website.doctype.web_page_view.web_page_view.make_view_log",
	"/api/method/frappe.desk.form.utils.add_comment",
	"/api/method/frappe.search.web_search",
	"/api/method/frappe.email.queue.unsubscribe",
	"/api/method/frappe.website.doctype.web_form.web_form.accept",
	"/api/method/frappe.core.doctype.user.user.test_password_strength",
	"/api/method/frappe.core.doctype.user.user.update_password",
	"/api/method/frappe.desk.desk_page.getpage",
	"/api/method/frappe.push_notification.auth_webhook",
	"/api/method/frappe.push_notification.subscribe",
	"/api/method/frappe.push_notification.unsubscribe",
	"/api/method/ping",
	"/api/method/login",
	"/api/method/logout",
	"/api/method/upload_file",
	"/api/method/mail.utils.user.get_user_tenant",
	"/api/method/mail.utils.user.generate_user_keys",
	"/api/method/mail.www.mail.get_context_for_dev",
	"/api/method/notification_relay.api.get_config",
	"/api/method/mail.client.doctype.address_book.address_book.add_address_book",
	"/api/method/mail.client.doctype.contact_card.contact_card.add_contact_card",
	"/api/method/mail.client.doctype.contact_card.contact_card.contact_card_add_to_address_book",
	"/api/method/mail.client.doctype.contact_card.contact_card.contact_card_remove_from_address_book",
	"/api/method/mail.client.doctype.contact_card.contact_card.delete_contact_cards",
]

ALLOWED_WILDCARD_PATHS = [
	"/api/method/mail.api.",
	"/api/method/frappe.client.",
	"/api/method/wiki.",
	"/api/method/frappe.integrations.oauth2_logins.",
	"/api/v2/document/",
]

DENIED_PATHS = ["/printview", "/printpreview"]

DENIED_WILDCARD_PATHS = ["/api/"]


def validate() -> None:
	if cmd := frappe.form_dict.cmd:
		raw_path = f"/api/method/{cmd}"
	else:
		raw_path = frappe.request.path

	path = unquote(raw_path)
	if not path.startswith("/"):
		path = "/" + path
	path = posixpath.normpath(path)

	if frappe.session.user != "Guest":
		user_type = frappe.get_cached_value("User", frappe.session.user, "user_type")

		# Allow unchecked access to System Users
		if user_type == "System User":
			return

	if path in DENIED_PATHS:
		frappe.throw(_("Access not allowed for this URL"), frappe.AuthenticationError)

	for denied in DENIED_WILDCARD_PATHS:
		if path.startswith(denied):
			for allowed in ALLOWED_WILDCARD_PATHS:
				if path.startswith(allowed):
					return
			if path in ALLOWED_PATHS:
				return

			frappe.throw(_("Access not allowed for this URL"), frappe.AuthenticationError)
