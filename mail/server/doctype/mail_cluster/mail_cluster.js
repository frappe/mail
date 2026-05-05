// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

const STORE_PRESET = {
	RocksDb: {
		store_path: '/var/lib/stalwart/rocksdb',
		store_blob_size: 16834,
		store_buffer_size: 134217728,
		store_pool_workers: 0,
	},
	Sqlite: {
		store_path: '/var/lib/stalwart/sqlite',
		store_pool_workers: 0,
		store_pool_max_connections: 10,
	},
	FoundationDb: {
		store_cluster_file: null,
		store_datacenter_id: null,
		store_machine_id: null,
		store_transaction_retry_delay: null,
		store_transaction_retry_limit: null,
		store_transaction_timeout: null,
	},
	PostgreSql: {
		store_timeout: '15s',
		store_use_tls: 0,
		store_allow_invalid_certs: 0,
		store_pool_max_connections: 10,
		store_pool_recycling_method: 'fast',
		store_host: null,
		store_port: 5432,
		store_database: 'frappe',
		store_auth_username: null,
		store_auth_secret: null,
		store_options: null,
	},
	MySql: {
		store_timeout: '15s',
		store_max_allowed_packet: 0,
		store_use_tls: 0,
		store_allow_invalid_certs: 0,
		store_pool_min_connections: 5,
		store_pool_max_connections: 10,
		store_host: null,
		store_port: 3306,
		store_database: 'frappe',
		store_auth_username: null,
		store_auth_secret: null,
	},
}

frappe.ui.form.on('Mail Cluster', {
	setup(frm) {
		frm.trigger('initialize_defaults')
	},

	refresh(frm) {
		frm.trigger('add_actions')
	},

	store_type(frm) {
		const defaults = STORE_PRESET[frm.doc.store_type]
		if (defaults) {
			Object.entries(defaults).forEach(([key, value]) => frm.set_value(key, value))
		}
	},

	initialize_defaults(frm) {
		if (!frm.doc.__islocal) return

		frappe.call({
			doc: frm.doc,
			method: 'initialize_defaults',
			freeze: true,
			freeze_message: __('Initializing Defaults...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		if (!frappe.user_roles.includes('System Manager')) return

		if (frm.doc.fallback_admin_password) {
			frm.add_custom_button(__('Show Password'), () => {
				frm.trigger('show_password')
			})
		}

		if (frm.doc.base_url) {
			frm.add_custom_button(
				__('Generate API Key'),
				() => {
					frm.trigger('generate_api_key')
				},
				__('Actions'),
			)
		}
	},

	show_password(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'get_fallback_admin_password',
			freeze: true,
			freeze_message: __('Getting Password...'),
			callback: (r) => {
				if (!r.exc) {
					frappe.msgprint(r.message)
				}
			},
		})
	},

	generate_api_key(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'generate_api_key',
			freeze: true,
			freeze_message: __('Generating API Key...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
