// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Outgoing Mail", {
    setup(frm) {
        frm.trigger("set_queries");
    },

	refresh(frm) {
        frm.trigger("hide_amend_button");
        frm.trigger("add_actions");
        frm.trigger("set_sender");
	},

    set_queries(frm) {
        frm.set_query("sender", () => ({
            query: "mail.mail.doctype.outgoing_mail.outgoing_mail.get_sender",
        }));
    },

    hide_amend_button(frm) {
		if (frm.doc.docstatus == 2) {
			frm.page.btn_primary.hide()
		}
	},

    add_actions(frm) {
        if (frm.doc.docstatus === 1) {
            if (frm.doc.status === "Pending") {
                frm.add_custom_button(__("Transfer Now"), () => {
                    frm.trigger("transfer_now");
                }, __("Actions"));
            }
            else if (frm.doc.status === "Failed") {
                frm.add_custom_button(__("Retry"), () => {
                    frm.trigger("retry_failed_mail");
                }, __("Actions"));
            }
            else if (["Transferred", "Queued", "Deferred"].includes(frm.doc.status)) {
                frm.add_custom_button(__("Get Status"), () => {
                    frm.trigger("get_outgoing_mails_status");
                }, __("Actions"));
            }
            else if (frm.doc.status === "Bounced" && has_common(frappe.user_roles, ["Administrator", "System Manager"])) {
                frm.add_custom_button(__("Retry"), () => {
                    frm.trigger("retry_bounced_mail");
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
        }
    },

    set_sender(frm) {
        if (!frm.doc.sender) {
            frappe.call({
                method: "mail.mail.doctype.outgoing_mail.outgoing_mail.get_default_sender",
                callback: (r) => {
                    if (r.message) {
                        frm.set_value("sender", r.message);
                    }
                }
            });
        }
    },

    transfer_now(frm) {
        frappe.call({
            doc: frm.doc,
            method: "transfer_now",
            freeze: true,
            freeze_message: __("Transferring..."),
            callback: (r) => {
                if (!r.exc) {
                    frm.refresh();
                }
            }
        });
    },

    retry_failed_mail(frm) {
        frappe.call({
            doc: frm.doc,
            method: "retry_failed_mail",
            freeze: true,
            freeze_message: __("Retrying..."),
            callback: (r) => {
                if (!r.exc) {
                    frm.refresh();
                }
            }
        });
    },

    get_outgoing_mails_status(frm) {
		frappe.call({
			method: "mail.mail.doctype.outgoing_mail.outgoing_mail.enqueue_get_outgoing_mails_status",
			freeze: true,
			freeze_message: __("Creating Job..."),
			callback: () => {
                frappe.show_alert({
                    message: __("{0} job has been created.", [__("Get Status").bold()]),
                    indicator: "green",
                });
            }
		});
	},

    retry_bounced_mail(frm) {
        frappe.call({
            doc: frm.doc,
            method: "retry_bounced_mail",
            freeze: true,
            freeze_message: __("Retrying..."),
            callback: (r) => {
                if (!r.exc) {
                    frm.refresh();
                }
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
