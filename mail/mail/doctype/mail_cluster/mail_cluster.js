// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

const STORES_PRESET = {
	RocksDB: {
		store_id: 'rocksdb',
		path: '/opt/stalwart/data',
		compression: 'LZ4',
		min_blob_size: 16834,
		write_buffer_size: 128,
		purge_frequency: '0 3 * * *',
	},
	FoundationDB: {
		store_id: 'foundationdb',
		compression: 'LZ4',
		purge_frequency: '0 3 * * *',
	},
	PostgreSQL: {
		store_id: 'postgresql',
		port: 5432,
		database: 'frappemail',
		timeout: 15,
		user: 'frappemail',
		compression: 'LZ4',
		purge_frequency: '0 3 * * *',
		pool_max_connections: 10,
	},
	mySQL: {
		store_id: 'mysql',
		port: 3306,
		database: 'frappemail',
		timeout: 15,
		user: 'frappemail',
		compression: 'LZ4',
		purge_frequency: '0 3 * * *',
		pool_max_connections: 10,
		pool_min_connections: 5,
	},
	SQLite: {
		store_id: 'sqlite',
		path: '/var/lib/data/index.sqlite3',
		compression: 'LZ4',
		purge_frequency: '0 3 * * *',
		pool_max_connections: 10,
	},
	'S3-compatible': {
		store_id: 's3',
		timeout: 15,
		bucket: 'frappemail',
		key_prefix: 'frappemail/',
		compression: 'LZ4',
		max_retries: 3,
		purge_frequency: '0 3 * * *',
	},
	'Redis/Memcached': {
		store_id: 'redis',
		redis_type: 'Redis Single Node',
		urls: 'redis://127.0.0.1',
		timeout: 15,
		user: 'frappemail',
		read_from_replicas: 1,
	},
	ElasticSearch: {
		store_id: 'elasticsearch',
		url: 'http://localhost:9200',
		user: 'frappemail',
		index_shards: 3,
		index_replicas: 0,
	},
	'Azure Blob Storage': {
		store_id: 'azure',
		timeout: 15,
		storage_account: 'frappe',
		container: 'mail',
		key_prefix: 'frappemail/',
		compression: 'LZ4',
		max_retries: 3,
		purge_frequency: '0 3 * * *',
	},
	Filesystem: {
		store_id: 'filesystem',
		path: '/var/lib/data/blobs',
		compression: 'LZ4',
		purge_frequency: '0 3 * * *',
		depth: 2,
	},
}

frappe.ui.form.on('Mail Cluster', {
	setup(frm) {
		frm.trigger('initialize_defaults')
	},

	refresh(frm) {
		frm.trigger('add_actions')
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

		if (frm.doc.enabled && !frm.is_dirty()) {
			frm.add_custom_button(
				__('Reload Configuration'),
				() => {
					frm.trigger('reload_config')
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

	reload_config(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'reload_config',
			freeze: true,
			freeze_message: __('Reloading Configuration...'),
			callback: (r) => {
				if (!r.exc) {
					frappe.show_alert(__('Configuration reloaded.'), 5)
					frm.refresh()
				}
			},
		})
	},
})

frappe.ui.form.on('Mail Server Store', {
	type(frm, cdt, cdn) {
		const row = locals[cdt][cdn]

		if (row.type) {
			const defaults = STORES_PRESET[row.type]
			if (defaults) {
				Object.entries(defaults).forEach(([key, value]) =>
					frappe.model.set_value(cdt, cdn, key, value),
				)
			}
		}

		refresh_field('stores')
	},

	redis_type() {
		refresh_field('stores')
	},
})
