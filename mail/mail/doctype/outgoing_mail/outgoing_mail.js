// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Outgoing Mail", {
	refresh(frm) {
        frm.trigger("hide_amend_button");
        frm.trigger("add_custom_buttons");
	},

    hide_amend_button(frm) {
		if (frm.doc.docstatus == 2) {
			frm.page.btn_primary.hide()
		}
	},

    add_custom_buttons(frm) {
        if (frm.doc.docstatus === 1) {
            if (frm.doc.status === "Failed") {
                frm.add_custom_button(__("Retry"), () => {
                    frm.trigger("retry");
                }, __("Actions"));
            }
        }
    },

    retry(frm) {
        frappe.call({
            doc: frm.doc,
            method: "resend",
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
