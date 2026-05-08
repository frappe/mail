// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sieve Script', {
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

	validate_script(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'validate_script',
			freeze: true,
			freeze_message: __('Validating Script...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
