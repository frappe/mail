// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Outgoing Mail", {
    setup(frm) {
        frm.trigger("set_queries");
        frm.trigger("disable_use_raw_html");
    },

	refresh(frm) {
        frm.trigger("hide_amend_button");
        frm.trigger("add_actions");
	},

    set_queries(frm) {
        frm.set_query("sender", (doc) => {
            return {
                query: "mail.mail.doctype.outgoing_mail.outgoing_mail.get_sender",
            };
        });
    },

    disable_use_raw_html(frm) {
        if (frm.is_new()) {
            frm.set_value("use_raw_html", 0);
        }
    },

    hide_amend_button(frm) {
		if (frm.doc.docstatus == 2) {
			frm.page.btn_primary.hide()
		}
	},

    add_actions(frm) {
        if (frm.doc.docstatus === 1) {
            if (frm.doc.status === "Failed") {
                frm.add_custom_button(__("Retry"), () => {
                    frm.trigger("retry");
                }, __("Actions"));
            }
            else if (frm.doc.status === "Transferred") {
                frm.add_custom_button(__("Get Delivery Status"), () => {
                    frm.trigger("get_delivery_status");
                }, __("Actions"));
            }
        }
    },

    retry(frm) {
        frappe.call({
            doc: frm.doc,
            method: "retry_send_mail",
            freeze: true,
            freeze_message: __("Retrying..."),
            callback: (r) => {
                if (!r.exc) {
                    frm.refresh();
                }
            }
        });
    },

    get_delivery_status(frm) {
		frappe.call({
			method: "mail.mail.doctype.outgoing_mail.outgoing_mail.get_delivery_status",
			args: {
				servers: frm.doc.server,
			},
			freeze: true,
			freeze_message: __("Getting Delivery Status..."),
			callback: () => {
                frappe.show_alert({
                    message: __("Get Delivery Status Job has been started in the background."),
                    indicator: "green",
                });
            }
		});
	},
});
