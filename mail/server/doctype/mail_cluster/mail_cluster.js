// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Cluster', {
	refresh(frm) {
		frm.trigger('add_actions')
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		if (!frappe.user_roles.includes('System Manager')) return

		if (frm.doc.recovery_admin_password) {
			frm.add_custom_button(__('Show Password'), () => {
				frm.trigger('show_password')
			})
		}

		if (frm.doc.base_url) {
			frm.add_custom_button(
				__('Generate API Key'),
				() => {
					frm.trigger('generate_api_key')
				},
				__('Actions'),
			)
		}
	},

	show_password(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'get_recovery_admin_password',
			freeze: true,
			freeze_message: __('Getting Password...'),
			callback: (r) => {
				if (!r.exc) {
					frappe.msgprint(r.message)
				}
			},
		})
	},

	generate_api_key(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'generate_api_key',
			freeze: true,
			freeze_message: __('Generating API Key...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
