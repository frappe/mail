import frappe


def execute() -> None:
	frappe.db.delete(
		"Has Role",
		{
			"role": "Mail User",
			"parenttype": "User",
			"parent": ("!=", "Administrator"),
		},
	)

	if frappe.db.exists("Role", "Mail User"):
		frappe.delete_doc("Role", "Mail User")
