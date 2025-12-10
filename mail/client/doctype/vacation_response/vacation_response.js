// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Vacation Response', {
	user(frm) {
		frm.trigger('get_vacation_response')
	},

	get_vacation_response(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'load_from_db',
			args: {},
			freeze: true,
			freeze_message: __('Loading Vacation Response...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
