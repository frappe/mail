// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Exchange', {
	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.trigger('add_actions')
			frm.trigger('set_account_options')
		}
	},

	user(frm) {
		frm.trigger('set_account_options')
	},

	add_actions(frm) {
		if (frm.doc.docstatus != 1) return
		if (!frappe.user_roles.includes('System Manager')) return

		if (['Failed'].includes(frm.doc.status)) {
			frm.add_custom_button(__('Retry'), () => frm.trigger('retry'), __('Actions'))
		}
	},

	set_account_options(frm) {
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

	retry(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'retry',
			freeze: true,
			freeze_message: __('Retrying...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
