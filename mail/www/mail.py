import frappe
from frappe import _

no_cache = 1


def get_context():
	frappe.db.commit()
	context = frappe._dict()
	context.boot = get_boot()
	return context


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(_("This method is only meant for developer mode"))
	return get_boot()


def get_boot():
	return frappe._dict(
		{
			"site_name": frappe.local.site,
			"csrf_token": frappe.sessions.get_csrf_token(),
			"push_relay_server_url": frappe.conf.get("push_relay_server_url") or "",
		}
	)
