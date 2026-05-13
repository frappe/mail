// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Settings', {
	setup(frm) {
		frm.trigger('set_queries')
	},

	refresh(frm) {
		frm.trigger('add_actions')
	},

	set_queries(frm) {
		frm.set_query('signup_domains', () => ({
			filters: {
				is_verified: 1,
				principal_type: 'Domain',
			},
		}))
	},

	dns_provider(frm) {
		if (frm.doc.dns_provider && frm.doc.dns_provider === 'GoDaddy') {
			frappe.msgprint({
				title: __('Limited Access to GoDaddy DNS APIs'),
				indicator: 'yellow',
				message: __(
					'Access to GoDaddy’s Domain Management and DNS APIs is restricted to accounts with 10 or more domains or an active Pro Discount Domain Club membership. Please verify that your account meets these requirements before proceeding.',
				),
			})
		}
	},

	add_actions(frm) {
		frm.add_custom_button(
			__('Generate JMAP Push Keys'),
			() => frm.trigger('generate_jmap_push_keys'),
			__('Actions'),
		)

		if (frappe.user.has_role('System Manager')) {
			frm.add_custom_button(
				__('Destroy Data Store'),
				() => frm.trigger('destroy_data_store'),
				__('Actions'),
			)

			frm.add_custom_button(
				__('Destroy Blob Store'),
				() => frm.trigger('destroy_blob_store'),
				__('Actions'),
			)
		}
	},

	generate_jmap_push_keys(frm) {
		frappe.confirm(
			__(
				'This will replace any existing JMAP Push keys. Existing push subscriptions must be recreated after generating new keys. Continue?',
			),
			() => {
				frappe.call({
					doc: frm.doc,
					method: 'generate_jmap_push_keys',
					freeze: true,
					freeze_message: __('Generating keys…'),
					callback: (r) => {
						if (!r.exc) frm.reload_doc()
					},
				})
			},
		)
	},

	destroy_data_store() {
		frappe.confirm(
			__(
				'This will permanently delete all data in the Data Store. This action cannot be undone. Do you want to continue?',
			),
			() => {
				frappe.call({
					method: 'mail.storage.destroy_data_store',
					freeze: true,
					freeze_message: __('Destroying Data Store…'),
					callback: (r) => {
						if (!r.exc) frappe.msgprint(__('Data Store destroyed successfully.'))
					},
				})
			},
		)
	},

	destroy_blob_store() {
		frappe.confirm(
			__(
				'This will permanently delete all data in the Blob Store. This action cannot be undone. Do you want to continue?',
			),
			() => {
				frappe.call({
					method: 'mail.storage.destroy_blob_store',
					freeze: true,
					freeze_message: __('Destroying Blob Store…'),
					callback: (r) => {
						if (!r.exc) frappe.msgprint(__('Blob Store destroyed successfully.'))
					},
				})
			},
		)
	},
})
