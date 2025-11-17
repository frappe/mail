// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('JMAP Push Verification Queue', {
	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.trigger('add_actions')
		}
	},

	add_actions(frm) {
		if (frm.doc.__islocal || !frappe.user_roles.includes('System Manager')) return

		if (frm.doc.status === 'Pending') {
			frm.add_custom_button(__('Process Now'), () => {
				frappe.call({
					doc: frm.doc,
					method: 'process',
					freeze: true,
					freeze_message: __('Processing...'),
					callback: (r) => {
						if (!r.exc) {
							frm.reload_doc()
						}
					},
				})
			})
		} else if (frm.doc.status === 'Failed') {
			frm.add_custom_button(__('Retry'), () => {
				frappe.call({
					doc: frm.doc,
					method: 'retry',
					freeze: true,
					freeze_message: __('Retrying...'),
					callback: (r) => {
						if (!r.exc) {
							frm.reload_doc()
						}
					},
				})
			})
		}
	},
})
