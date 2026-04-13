import frappe


def execute() -> None:
	frappe.db.delete(
		"Has Role",
		{
			"role": "Mail Admin",
			"parenttype": "User",
			"parent": ("!=", "Administrator"),
		},
	)
