// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
frappe.ui.form.on("DNS Record", {
	refresh(frm) {
        frm.trigger("add_actions");
	},
    add_actions(frm) {
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__("Verify DNS Record"), () => {
                frm.trigger("verify_dns_record");
            }, __("Actions"));
        }
    },
    verify_dns_record(frm) {
        frappe.call({
            doc: frm.doc,
            method: "verify_dns_record",
            args: {
                save: true,
            },
            freeze: true,
            freeze_message: __("Verifying DNS Record..."),
            callback: (r) => {
                if (!r.exc) {
                    frm.refresh();
                }
            }
        });
    },
});