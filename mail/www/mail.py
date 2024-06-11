import frappe
from frappe.utils.telemetry import capture

def get_context(context):
    context.no_cache = 1
    csrf_token = frappe.sessions.get_csrf_token()
    frappe.db.commit()
    context = frappe._dict()
    context.boot.csrf_token = csrf_token
    if frappe.session.user != "Guest":
        capture("active_site", "mail")
    return context