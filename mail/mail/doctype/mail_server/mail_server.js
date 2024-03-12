// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Server", {
	refresh(frm) {
		frm.trigger("add_actions");
	},

	add_actions(frm) {
        if (frm.doc.incoming) {
            frm.add_custom_button(__("Update Virtual Domains"), () => {
                frm.trigger("update_virtual_domains");
            }, __("Actions"));
            frm.add_custom_button(__("Update Virtual Mailboxes"), () => {
                frm.trigger("update_virtual_mailboxes");
            }, __("Actions"));
        }
    },

	update_virtual_domains(frm) {
        frappe.call({
			method: "mail.mail.doctype.mail_domain.mail_domain.update_virtual_domains",
			args: {
				servers: frm.doc.server,
			},
			freeze: true,
			freeze_message: __("Updating Virtual Domains..."),
		});
    },

	update_virtual_mailboxes(frm) {
        frappe.call({
			method: "mail.mail.doctype.mailbox.mailbox.update_virtual_mailboxes",
			args: {
				servers: frm.doc.server,
			},
			freeze: true,
			freeze_message: __("Updating Virtual Mailboxes..."),
		});
    },
});
