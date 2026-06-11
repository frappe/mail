// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Cluster', {
	setup(frm) {
		frm.trigger('set_queries')
	},

	refresh(frm) {
		frm.trigger('add_actions')
	},

	set_queries(frm) {
		frm.set_query(
			'data_store',
			() => ({
				filters: {
					type: ['in', ['RocksDb', 'Sqlite', 'FoundationDb', 'PostgreSql', 'MySql']],
				},
			}),
			frm.set_query('blob_store', () => ({
				filters: {
					type: ['in', ['Default', 'RocksDb', 'S3', 'Azure', 'FileSystem']],
				},
			})),
			frm.set_query('search_store', () => ({
				filters: {
					type: ['in', ['Default', 'RocksDb', 'ElasticSearch', 'Meilisearch']],
				},
			})),
			frm.set_query('in_memory_store', () => ({
				filters: {
					type: ['in', ['Default', 'RocksDb', 'Redis', 'RedisCluster']],
				},
			})),
		)
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		if (!frappe.user_roles.includes('System Manager')) return

		if (frm.doc.recovery_admin_password) {
			frm.add_custom_button(__('Show Password'), () => {
				frm.trigger('show_password')
			})
		}
	},

	show_password(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'get_recovery_admin_password',
			freeze: true,
			freeze_message: __('Getting Password...'),
			callback: (r) => {
				if (!r.exc) {
					frappe.msgprint(r.message)
				}
			},
		})
	},
})
