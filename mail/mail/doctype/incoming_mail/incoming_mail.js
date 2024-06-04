// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Incoming Mail", {
	refresh(frm) {
        frm.trigger("add_actions");
	},

    add_actions(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Reply"), () => {
                frm.events.reply(frm, all=false);
            }, __("Actions"));
            frm.add_custom_button(__("Reply All"), () => {
                frm.events.reply(frm, all=true);
            }, __("Actions"));

            frm.page.set_inner_btn_group_as_primary(__("Actions"));
        }
    },

    reply(frm, all) {
        frappe.model.open_mapped_doc({
			method: "mail.mail.doctype.incoming_mail.incoming_mail.reply_to_mail",
			frm: frm,
            args: {
                all: all,
            },
		});
    }
});
