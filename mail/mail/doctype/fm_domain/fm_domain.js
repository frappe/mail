// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("FM Domain", {
	refresh(frm) {
        frm.trigger("set_domain_owner");
        frm.trigger("make_records_table_read_only");
	},

    make_records_table_read_only(frm) {
        ["sending_records", "receiving_records", "tracking_records"].forEach((field) => {
            frm.set_df_property(field, "cannot_add_rows", true);
            frm.set_df_property(field, "cannot_delete_rows", true);
        });  
    },

    set_domain_owner(frm) {
        if (frm.doc.__islocal && !frm.doc.domain_owner && frappe.session.user) {
            frm.set_value("domain_owner", frappe.session.user);
        }
    }
});
