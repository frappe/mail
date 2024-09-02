import frappe


def execute():
	for mail_domain in frappe.db.get_all("Mail Domain", fields=["name"], pluck="name"):
		mail_domain = frappe.get_doc("Mail Domain", mail_domain)

		if not mail_domain.get("dkim_private_key") or not mail_domain.get("dkim_public_key"):
			continue

		dkim_key = frappe.new_doc("DKIM Key")
		dkim_key.domain_name = mail_domain.name
		dkim_key.key_size = mail_domain.dkim_key_size
		dkim_key.private_key = mail_domain.get_password("dkim_private_key")
		dkim_key.public_key = mail_domain.dkim_public_key
		dkim_key.ignore_validate = True
		dkim_key.save(ignore_permissions=True)
