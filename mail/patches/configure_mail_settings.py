import frappe

CONFIG_KEY_FIELD_MAP = {
	# JMAP
	"server_url": None,
	"api_key": None,
	"username": None,
	"password": None,
	# SpamAssassin
	"spamd_host": None,
	"spamd_port": None,
	"spamd_scanning_mode": None,
	"spamd_hybrid_scanning_threshold": None,
	# Defaults
	"default_dns_ttl": None,
	"default_mail_quota": "default_disk_quota_gb",
	"gravatar_default_avatar": "default_gravatar",
	"stalwart_version": None,
	"stalwart_cli_version": None,
	"storage_shard_count": None,
	# Logs
	"push_log_file_count": None,
	"push_log_level": None,
	"push_log_max_size": "push_log_max_file_size",
	"storage_log_file_count": None,
	"storage_log_level": None,
	"storage_log_max_size": "storage_log_max_file_size",
	# Limits
	"exchange_max_export": None,
	"exchange_max_import": None,
	"exchange_export_batch_size": None,
	"max_email_sync": None,
	"max_message_payload_size": "max_message_payload_size_mb",
	"max_push_notifications": None,
	"process_pending_emails_batch_size": None,
	"process_pending_emails_max_batch_size": None,
	# Timeouts
	"ansible_play_timeout": None,
	"server_job_timeout": None,
	"server_deployment_timeout": None,
	"scan_message_timeout": None,
	"process_pending_emails_timeout": None,
	"stalwart_cli_command_timeout": None,
	"exchange_export_timeout": None,
	"exchange_import_timeout": None,
	"fetch_lock_timeout": None,
	"lock_acquire_timeout": None,
	"lock_timeout": None,
}


def execute() -> None:
	mail_conf = frappe.conf.mail or {}

	meta = frappe.get_meta("Mail Settings")
	settings = frappe.get_doc("Mail Settings")

	for key, field in CONFIG_KEY_FIELD_MAP.items():
		value = mail_conf.get(key) or meta.get_field(field or key).default
		if value is not None:
			if key == "default_mail_quota":
				value = int(int(value) // 1024**3)

			setattr(settings, field or key, value)

	settings.save()
