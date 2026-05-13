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
})
