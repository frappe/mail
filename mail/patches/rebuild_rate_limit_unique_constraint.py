import frappe


def execute() -> None:
	"""Drop the existing `unique_rate_limit` constraint so it is recreated with the
	new `value` column (see Rate Limit.on_doctype_update) during model sync."""

	table = "tabRate Limit"
	constraint = "unique_rate_limit"

	constraints = frappe.qb.Schema("information_schema").table_constraints
	exists = (
		frappe.qb.from_(constraints)
		.select(constraints.constraint_name)
		.where(
			(constraints.table_name == table)
			& (constraints.constraint_type == "UNIQUE")
			& (constraints.constraint_name == constraint)
		)
		.run()
	)
	if exists:
		frappe.db.sql_ddl(f"alter table `{table}` drop index `{constraint}`")
