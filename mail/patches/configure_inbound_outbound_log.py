import frappe

CONFIG_KEY_FIELD_MAP = {
	# Inbound
	"inbound_log_file_count": None,
	"inbound_log_level": None,
	"inbound_log_max_file_size": None,
	# Outbound
	"outbound_log_file_count": None,
	"outbound_log_level": None,
	"outbound_log_max_file_size": None,
}


def execute() -> None:
	meta = frappe.get_meta("Mail Settings")
	settings = frappe.get_doc("Mail Settings")

	for key, field in CONFIG_KEY_FIELD_MAP.items():
		value = meta.get_field(field or key).default
		if value is not None:
			setattr(settings, field or key, value)

	settings.save()
