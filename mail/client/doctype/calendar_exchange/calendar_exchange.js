// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Calendar Exchange', {
	refresh(frm) {
		frm.trigger('set_account_options')
		if (!frm.doc.__islocal) {
			frm.trigger('add_actions')
		}
	},

	user(frm) {
		frm.set_value('account_id', null)
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
