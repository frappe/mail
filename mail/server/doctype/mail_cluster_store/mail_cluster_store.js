// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

const STORE_PRESET = {
	RocksDb: {
		path: '/etc/stalwart/data',
		blob_size: 16834,
		buffer_size: 134217728,
		pool_workers: 1,
	},
	Sqlite: {
		path: '/etc/stalwart/data',
		pool_workers: 1,
		pool_max_connections: 10,
	},
	FoundationDb: {
		cluster_file: null,
		datacenter_id: null,
		machine_id: null,
		transaction_retry_delay: null,
		transaction_retry_limit: null,
		transaction_timeout: null,
	},
	PostgreSql: {
		timeout: '15s',
		use_tls: 0,
		allow_invalid_certs: 0,
		pool_max_connections: 10,
		pool_recycling_method: 'fast',
		host: null,
		port: 5432,
		database: 'frappe',
		auth_username: null,
		auth_secret: null,
		options: null,
	},
	MySql: {
		timeout: '15s',
		max_allowed_packet: 0,
		use_tls: 0,
		allow_invalid_certs: 0,
		pool_min_connections: 5,
		pool_max_connections: 10,
		host: null,
		port: 3306,
		database: 'frappe',
		auth_username: null,
		auth_secret: null,
	},
}

frappe.ui.form.on('Mail Cluster Store', {
	type(frm) {
		const defaults = STORE_PRESET[frm.doc.type]
		if (defaults) {
			Object.entries(defaults).forEach(([key, value]) => frm.set_value(key, value))
		}
	},
})
