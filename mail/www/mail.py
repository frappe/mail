import frappe


def get_context():
	frappe.db.commit()
	context = frappe._dict()
	context.boot = get_boot()
	return context


def get_boot():
	return frappe._dict(
		{
			"site_name": frappe.local.site,
			"csrf_token": frappe.sessions.get_csrf_token(),
			"push_relay_server_url": frappe.conf.get("push_relay_server_url") or "",
		}
	)
