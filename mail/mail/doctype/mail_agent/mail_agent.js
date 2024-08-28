// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Agent", {
	incoming(frm) {
		if (frm.doc.incoming) {
			frm.set_value("outgoing", 0);
		}
	},

	outgoing(frm) {
		if (frm.doc.outgoing) {
			frm.set_value("incoming", 0);
		}
	},
});
