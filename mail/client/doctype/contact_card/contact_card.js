// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Contact Card', {
	refresh(frm) {
		frm.trigger('set_queries')
	},

	user(frm) {
		if (frm.doc.user) {
			frappe.call({
				method: 'mail.jmap.get_user_accounts',
				args: {
					user: frm.doc.user,
				},
				callback: (r) => {
					if (r.message) {
						frm.set_df_property('account', 'options', r.message)
						frm.refresh_field('account')
					}
				},
			})
		} else {
			frm.set_df_property('account', 'options', [])
			frm.refresh_field('account')
		}
	},

	set_queries(frm) {
		frm.set_query('address_book', 'address_books', () => ({
			query: 'mail.utils.query.get_account_address_books',
			filters: {
				account: frm.doc.account,
			},
		}))
	},
})
