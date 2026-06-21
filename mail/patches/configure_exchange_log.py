import frappe

CONFIG_KEY_FIELD_MAP = {
	# Exchange
	"exchange_log_file_count": None,
	"exchange_log_level": None,
	"exchange_log_max_file_size": None,
}


def execute() -> None:
	meta = frappe.get_meta("Mail Settings")
	settings = frappe.get_doc("Mail Settings")

	for key, field in CONFIG_KEY_FIELD_MAP.items():
		value = meta.get_field(field or key).default
		if value is not None:
			setattr(settings, field or key, value)

	settings.flags.ignore_mandatory = 1
	settings.save()
