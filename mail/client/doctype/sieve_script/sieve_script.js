// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sieve Script', {
	refresh(frm) {
		frm.trigger('set_account_options')
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
