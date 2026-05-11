// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('User Settings', {
	refresh(frm) {
		frm.trigger('add_actions')
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		if (frm.doc.session_state) {
			frm.add_custom_button(__('Clear JMAP Session'), () => {
				frm.trigger('clear_jmap_session')
			})
		}

		if (frappe.user_roles.includes('Administrator') && frm.doc.app_password) {
			frm.add_custom_button(__('Show App Password'), () => {
				frm.trigger('show_app_password')
			})
		}
	},

	clear_jmap_session(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'clear_jmap_session',
			freeze: true,
			freeze_message: __('Clearing JMAP Session...'),
			callback: (r) => {
				if (!r.exc) {
					frm.reload_doc()
					frappe.show_alert(
						{
							message: __('JMAP Session cleared successfully'),
							indicator: 'green',
						},
						3,
					)
				}
			},
		})
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
