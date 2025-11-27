// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Push Subscription', {
	refresh(frm) {
		frm.trigger('add_actions')
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		frm.add_custom_button(
			__('Renew'),
			() => {
				frm.trigger('renew')
			},
			__('Actions'),
		)
	},

	renew(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'renew',
			freeze: true,
			freeze_message: __('Renewing...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
