// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Contact Card', {
	refresh(frm) {
		frm.trigger('set_account_options')
		frm.trigger('set_queries')
	},

	user(frm) {
		frm.set_value('account_id', null)
		frm.trigger('set_account_options')
	},

	set_account_options(frm) {
		if (frm.doc.user) {
			frappe.call({
				method: 'mail.jmap.get_user_account_ids',
				args: {
					user: frm.doc.user,
				},
				callback: (r) => {
					frm.set_df_property('account_id', 'options', r.message || [])
					frm.refresh_field('account_id')
				},
			})
		} else {
			frm.set_df_property('account_id', 'options', [])
			frm.refresh_field('account_id')
		}
	},

	set_queries(frm) {
		frm.set_query('address_book', 'address_books', () => ({
			query: 'mail.utils.query.get_account_address_books',
			filters: {
				account: `${frm.doc.user}:${frm.doc.account_id}`,
			},
		}))
	},
})
