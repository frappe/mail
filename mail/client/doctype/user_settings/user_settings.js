// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('User Settings', {
	refresh(frm) {
		frm.trigger('add_actions')
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		if (!frappe.user_roles.includes('Administrator')) return

		if (frm.doc.app_password) {
			frm.add_custom_button(__('Show App Password'), () => {
				frm.trigger('show_app_password')
			})
		}
	},

	show_app_password(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'show_app_password',
			freeze: true,
			freeze_message: __('Getting Password...'),
			callback: (r) => {
				if (!r.exc) {
					frappe.msgprint(r.message)
				}
			},
		})
	},
})
