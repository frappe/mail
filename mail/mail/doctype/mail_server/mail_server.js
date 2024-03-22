// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Server", {
	refresh(frm) {
		frm.trigger("add_actions");
	},

	add_actions(frm) {
        if (frm.doc.incoming) {
			frm.add_custom_button(__("Get Delivery Status"), () => {
                frm.trigger("get_delivery_status");
            }, __("Actions"));

			frm.add_custom_button(__("Get Incoming Mails"), () => {
                frm.trigger("get_incoming_mails");
            }, __("Actions"));

            frm.add_custom_button(__("Update Virtual Domains"), () => {
                frm.trigger("update_virtual_domains");
            }, __("Actions"));

            frm.add_custom_button(__("Update Virtual Mailboxes"), () => {
                frm.trigger("update_virtual_mailboxes");
            }, __("Actions"));
        }
    },

	get_delivery_status(frm) {
		frappe.call({
			method: "mail.mail.doctype.outgoing_mail.outgoing_mail.get_delivery_status",
			args: {
				servers: frm.doc.server,
			},
			freeze: true,
			freeze_message: __("Getting Delivery Status..."),
			callback: function() {
                frappe.msgprint(__("Get Delivery Status Job has been started in the background."));
            }
		});
	},

	get_incoming_mails(frm) {
        frappe.call({
			method: "mail.mail.doctype.incoming_mail.incoming_mail.get_incoming_mails",
			args: {
				servers: frm.doc.server,
			},
			freeze: true,
			freeze_message: __("Receiving Mails..."),
			callback: function() {
                frappe.msgprint(__("Get Incoming Mails Job has been started in the background."));
            }
		});
    },

	update_virtual_domains(frm) {
        frappe.call({
			method: "mail.mail.doctype.mail_domain.mail_domain.update_virtual_domains",
			args: {
				servers: frm.doc.server,
			},
			freeze: true,
			freeze_message: __("Updating Virtual Domains..."),
			callback: function() {
				frappe.msgprint(__("Update Virtual Domains Job has been started in the background."));
			}
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
			callback: function() {
				frappe.msgprint(__("Update Virtual Mailboxes Job has been started in the background."));
			}
		});
    },
});
