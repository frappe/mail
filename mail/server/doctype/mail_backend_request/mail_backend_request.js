// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Backend Request', {
	setup(frm) {
		frm.trigger('set_queries')
	},

	set_queries(frm) {
		frm.set_query('backend_name', () => ({
			filters: {
				enabled: 1,
			},
		}))
	},
})
