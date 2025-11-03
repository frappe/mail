// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Server Deployment', {
	setup(frm) {
		frm.trigger('set_queries')
	},

	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.disable_save()
			frm.trigger('add_actions')
		}
	},

	set_queries(frm) {
		frm.set_query('config', () => ({
			filters: {
				server: frm.doc.server,
			},
		}))
	},

	add_actions(frm) {
		if (!frappe.user_roles.includes('System Manager')) return

		if (frm.doc.status === 'Failed') {
			frm.add_custom_button(__('Retry'), () => frm.trigger('retry'), __('Actions'))
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
