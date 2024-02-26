// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Agent Job", {
	refresh(frm) {
        frm.trigger("add_actions");
	},

    add_actions(frm) {
        if (frm.doc.status === "Failed") {
            frm.add_custom_button(__("Retry"), () => {
                frm.trigger("retry");
            }, __("Actions"));
        }
    },

    retry(frm) {
        frappe.call({
            doc: frm.doc,
            method: "rerun",
            freeze: true,
            freeze_message: __("Retrying..."),
            callback: (r) => {
                if (!r.exc) {
                    frm.refresh();
                }
            }
        });
    },
});
