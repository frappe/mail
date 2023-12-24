// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("FM Domain", {
	refresh(frm) {
        frm.trigger("set_domain_owner");
	},

    set_domain_owner(frm) {
        if (frm.doc.__islocal && !frm.doc.domain_owner && frappe.session.user) {
            frm.set_value("domain_owner", frappe.session.user);
        }
    }
});
