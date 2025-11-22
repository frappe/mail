// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Contact Card', {
	refresh(frm) {
		frm.trigger('set_queries')
	},

	set_queries(frm) {
		frm.set_query('address_book', 'address_books', () => ({
			query: 'mail.utils.query.get_user_address_books',
			filters: {
				user: frm.doc.user,
			},
		}))
	},
})
