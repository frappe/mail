import frappe
from frappe.apps import get_apps as get_permitted_apps
from frappe.translate import get_all_translations
from frappe.utils.caching import redis_cache

from mail.utils.cache import get_personal_signup_domains


@frappe.whitelist(allow_guest=True)
def get_signup_settings() -> dict:
	"""Returns client signup settings."""

	return {
		"allow_business_signup": frappe.db.get_single_value("Mail Settings", "allow_business_signup"),
		"allow_personal_signup": frappe.db.get_single_value("Mail Settings", "allow_personal_signup"),
	}


@frappe.whitelist(allow_guest=True)
def get_signup_domains() -> list:
	"""Returns personal signup domains."""

	return get_personal_signup_domains()


@frappe.whitelist(allow_guest=True)
def get_branding() -> dict:
	"""Returns branding information."""

	return {
		"brand_name": frappe.db.get_single_value("Website Settings", "app_name"),
		"brand_html": frappe.db.get_single_value("Website Settings", "brand_html"),
		"favicon": frappe.db.get_single_value("Website Settings", "favicon"),
	}


@frappe.whitelist(allow_guest=True)
def get_translations() -> dict:
	"""Returns translations for the current user's language."""

	if frappe.session.user != "Guest":
		language = frappe.db.get_value("User", frappe.session.user, "language")
	else:
		language = frappe.db.get_single_value("System Settings", "language")

	return get_all_translations(language)


@frappe.whitelist()
@redis_cache()
def get_apps():
	apps = get_permitted_apps()
	desk = {
		"name": "frappe",
		"logo": "/assets/mail/images/desk.png",
		"title": "Desk",
		"route": "/app",
	}

	apps.insert(0, desk)

	return apps
