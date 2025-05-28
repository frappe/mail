import frappe
from frappe.model.utils.rename_field import rename_field

FIELD_RENAMES = {
	"Mail Cluster": {
		"cluster": "hostname",
		"admin_username": "fallback_admin_user",
		"admin_password": "fallback_admin_password",
		"admin_password_hash": "fallback_admin_secret",
		"cluster_encryption_key": "cluster_key",
		"proxy_trusted_networks": "server_proxy_trusted_networks",
		"directory_storage": "storage_directory",
		"data_storage": "storage_data",
		"enable_encryption_at_rest": "email_encryption_enable",
		"encrypt_on_append": "email_encryption_append",
		"blob_storage": "storage_blob",
		"fts_storage": "storage_fts",
		"default_language": "storage_full_text_default_language",
		"in_memory_storage": "storage_lookup",
		"jmap_frequency_cron": "account_purge_frequency",
		"jmap_changes_history_days": "changes_max_history",
		"jmap_trash_auto_expunge_days": "email_auto_expunge",
	},
	"Mail Server": {
		"server": "hostname",
		"cluster_bind_address": "cluster_bind_addr",
		"cluster_advertise_address": "cluster_advertise_addr",
	},
	"Mail Server Store": {
		"hostname": "host",
		"redis_server_type": "redis_type",
		"redis_urls": "urls",
		"max_allowed_packet_bytes": "max_allowed_packet",
		"timeout_seconds": "timeout",
		"bucket_name": "bucket",
		"storage_account_name": "storage_account",
		"username": "user",
		"s3_access_key": "access_key",
		"s3_secret_key": "secret_key",
		"s3_security_token": "security_token",
		"azure_sas_token": "sas_token",
		"min_blob_size_bytes": "min_blob_size",
		"write_buffer_size_mb": "write_buffer_size",
		"retry_limit": "max_retries",
		"nested_depth": "depth",
		"purge_frequency_cron": "purge_frequency",
		"machine_id": "machine",
		"data_center_id": "datacenter",
		"cluster_retries": "retry_total",
		"cluster_max_wait_ms": "retry_max_wait",
		"cluster_min_wait_ms": "retry_min_wait",
		"cluster_read_from_replicas": "read_from_replicas",
		"transaction_timeout_seconds": "transaction_timeout",
		"transaction_max_retry_delay_seconds": "transaction_max_retry_delay",
		"enable_tls": "tls_enable",
		"allow_invalid_certs": "tls_allow_invalid_certs",
		"thread_pool_size": "workers",
		"max_connections": "pool_max_connections",
		"min_connections": "pool_min_connections",
		"number_of_shards": "index_shards",
		"number_of_replicas": "index_replicas",
	},
	"Mail Server Listener": {"bind_addresses": "bind", "implicit_tls": "tls_implicit"},
	"Mail Server ACME Provider": {
		"challenge_type": "challenge",
		"directory_url": "directory",
		"renew_before_days": "renew_before",
		"subject_names": "domains",
		"contact_emails": "contact",
		"key_id": "eab_kid",
		"hmac_key": "eab_hmac_key",
	},
	"Mail Server TLS Certificate": {
		"certificate_path": "cert_path",
		"certificate": "cert",
	},
}


def execute() -> None:
	for doctype, renames in FIELD_RENAMES.items():
		for old_field, new_field in renames.items():
			if frappe.db.has_column(doctype, old_field):
				rename_field(doctype, old_field, new_field)
