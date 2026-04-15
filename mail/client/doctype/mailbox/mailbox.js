// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mailbox', {
	refresh(frm) {
		frm.trigger('set_queries')
	},

	set_queries(frm) {
		frm.set_query('_parent', () => ({
			query: 'mail.utils.query.get_account_mailboxes',
			filters: {
				account: frm.doc.account,
			},
		}))
	},
})
