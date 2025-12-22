// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Exchange', {
	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.trigger('add_actions')
		}

		frappe.realtime.on('mail_exchange_progress', (data) => {
			if (data.exchange === frm.doc.name && data.progress) {
				frm.dashboard.show_progress(data.title, data.progress, data.msg)
				if (data.progress >= 100) {
					frm.dashboard.hide_progress(data.title)
				}
			}
		})
	},

	add_actions(frm) {
		if (frm.doc.docstatus != 1) return
		if (!frappe.user_roles.includes('System Manager')) return

		if (['Failed'].includes(frm.doc.status)) {
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
