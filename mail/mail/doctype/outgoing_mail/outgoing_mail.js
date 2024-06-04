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
            else if (["Transferred", "Queued", "Deferred"].includes(frm.doc.status)) {
                frm.add_custom_button(__("Sync Status"), () => {
                    frm.trigger("sync_outgoing_mails_status");
                }, __("Actions"));
            }
            else if (frm.doc.status === "Sent") {
                frm.add_custom_button(__("Reply"), () => {
                    frm.events.reply(frm, all=false);
                }, __("Actions"));
                frm.add_custom_button(__("Reply All"), () => {
                    frm.events.reply(frm, all=true);
                }, __("Actions"));
            }

            frm.page.set_inner_btn_group_as_primary(__("Actions"));
        }
    },

    retry(frm) {
        frappe.call({
            doc: frm.doc,
            method: "retry_transfer_mail",
            freeze: true,
            freeze_message: __("Retrying..."),
            callback: (r) => {
                if (!r.exc) {
                    frm.refresh();
                }
            }
        });
    },

    sync_outgoing_mails_status(frm) {
		frappe.call({
			method: "mail.mail.doctype.outgoing_mail.outgoing_mail.sync_outgoing_mails_status",
			args: {
				agents: frm.doc.agent,
			},
			freeze: true,
			freeze_message: __("Getting Delivery Status..."),
			callback: () => {
                frappe.show_alert({
                    message: __("Sync Outgoing Mails Status Job has been started in the background."),
                    indicator: "green",
                });
            }
		});
	},

    reply(frm, all) {
        frappe.model.open_mapped_doc({
			method: "mail.mail.doctype.outgoing_mail.outgoing_mail.reply_to_mail",
			frm: frm,
            args: {
                all: all,
            },
		});
    }
});
