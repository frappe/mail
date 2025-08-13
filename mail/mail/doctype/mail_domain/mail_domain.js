// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Domain', {
	refresh(frm) {
		frm.trigger('add_actions')
	},

	add_actions(frm) {
		if (!frm.doc.__islocal) {
			frm.add_custom_button(
				__('Verify DNS Records'),
				() => {
					frm.trigger('verify_dns_records')
				},
				__('Actions'),
			)
		}
	},

	verify_dns_records(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'verify_dns_records',
			args: {},
			freeze: true,
			freeze_message: __('Verifying DNS Records...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
