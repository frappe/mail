// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Address Book', {
	refresh(frm) {
		frm.trigger('set_queries')
	},

	set_queries(frm) {
		frm.set_query('account', () => ({
			query: 'mail.utils.query.get_user_accounts',
			filters: {
				user: frappe.session.user,
			},
		}))
	},
})
