import frappe


def execute() -> None:
	"""Drop the existing `unique_rate_limit` constraint so it is recreated with the
	new `value` column (see Rate Limit.on_doctype_update) during model sync."""

	table = "tabRate Limit"
	constraint = "unique_rate_limit"

	exists = frappe.db.sql(
		"""select CONSTRAINT_NAME from information_schema.TABLE_CONSTRAINTS
		where table_name = %s and constraint_type = 'UNIQUE' and CONSTRAINT_NAME = %s""",
		(table, constraint),
	)
	if exists:
		frappe.db.sql_ddl(f"alter table `{table}` drop index `{constraint}`")
