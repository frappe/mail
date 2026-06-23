// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sieve Script', {
	validate_script(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'validate_script',
			freeze: true,
			freeze_message: __('Validating Script...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
