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
	FoundationDb: {},
	PostgreSql: {
		timeout: 15,
		pool_max_connections: 10,
		pool_recycling_method: 'fast',
		port: 5432,
		database: 'frappe',
	},
	MySql: {
		timeout: 15,
		pool_min_connections: 5,
		pool_max_connections: 10,
		port: 3306,
		database: 'frappe',
	},
	S3: {
		timeout: 30,
		max_retries: 3,
		verify_after_write: 1,
	},
	Azure: {
		timeout: 30,
		max_retries: 3,
	},
	FileSystem: {
		path: '/etc/stalwart/blob',
		depth: 2,
	},
	ElasticSearch: {
		timeout: 30,
		num_replicas: 0,
		num_shards: 3,
		http_headers: '{}',
	},
	Meilisearch: {
		timeout: 30,
		poll_interval: 0.5,
		max_retries: 120,
		fail_on_timeout: 1,
		http_headers: '{}',
	},
	Redis: {
		timeout: 10,
		pool_max_connections: 10,
		pool_timeout_create: 30,
		pool_timeout_wait: 30,
		pool_timeout_recycle: 30,
	},
	RedisCluster: {
		timeout: 10,
		urls: '["redis://127.0.0.1"]',
		read_from_replicas: 1,
		pool_max_connections: 10,
		pool_timeout_create: 30,
		pool_timeout_wait: 30,
		pool_timeout_recycle: 30,
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
