import frappe


def execute() -> None:
	frappe.db.delete(
		"Has Role",
		{
			"role": "Mail User",
			"parenttype": "User",
		},
	)
