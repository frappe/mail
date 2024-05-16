import frappe


def after_install() -> None:
	create_postmaster()


def create_postmaster() -> None:
	"""Creates postmaster user if not exists."""

	if not frappe.db.exists("User", "postmaster@frappemail.com"):
		user = frappe.new_doc("User")
		user.email = "postmaster@frappemail.com"
		user.first_name = "Postmaster"
		user.user_type = "System User"
		user.send_welcome_email = 0
		user.add_roles("Postmaster")
		user.insert(ignore_permissions=True)
