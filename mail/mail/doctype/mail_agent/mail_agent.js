// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Agent", {
	refresh(frm) {
		frm.trigger("add_actions");
	},

	incoming(frm) {
		if (frm.doc.incoming) {
			frm.set_value("outgoing", 0);
		}
	},

	outgoing(frm) {
		if (frm.doc.outgoing) {
			frm.set_value("incoming", 0);
		}
	},

	add_actions(frm) {
		if (!frm.doc.__islocal) {
			if (frm.doc.outgoing) {
				frm.add_custom_button(__("Sync Outgoing Mails Status"), () => {
					frm.trigger("sync_outgoing_mails_status");
				}, __("Actions"));
			}

			if (frm.doc.incoming) {
				frm.add_custom_button(__("Sync Incoming Mails"), () => {
					frm.trigger("sync_incoming_mails");
				}, __("Actions"));

				frm.add_custom_button(__("Sync Mail Domains"), () => {
					frm.trigger("sync_mail_domains");
				}, __("Actions"));

				frm.add_custom_button(__("Sync Mailboxes"), () => {
					frm.trigger("sync_mailboxes");
				}, __("Actions"));

				frm.add_custom_button(__("Sync Mail Aliases"), () => {
					frm.trigger("sync_mail_aliases");
				}, __("Actions"));
			}
		}
    },

	sync_outgoing_mails_status(frm) {
		frappe.call({
			method: "mail.mail.doctype.outgoing_mail.outgoing_mail.sync_outgoing_mails_status",
			args: {
				agents: frm.doc.agent,
			},
			freeze: true,
			freeze_message: __("Creating Mail Agent Job..."),
			callback: () => {
				frappe.show_alert({
					message: __("{0} job has been created.", [__("Sync Status").bold()]),
					indicator: "green",
				});
			}
		});
	},

	sync_incoming_mails(frm) {
        frappe.call({
			method: "mail.mail.doctype.incoming_mail.incoming_mail.sync_incoming_mails",
			args: {
				agents: frm.doc.agent,
			},
			freeze: true,
			freeze_message: __("Creating Mail Agent Job..."),
			callback: () => {
				frappe.show_alert({
					message: __("{0} job has been created.", [__("Sync Mails").bold()]),
					indicator: "green",
				});
			}
		});
    },

	sync_mail_domains(frm) {
        frappe.call({
			method: "mail.mail.doctype.mail_domain.mail_domain.sync_mail_domains",
			args: {
				agents: frm.doc.agent,
			},
			freeze: true,
			freeze_message: __("Creating Mail Agent Job..."),
			callback: () => {
				frappe.show_alert({
					message: __("{0} job has been created.", [__("Sync Mail Domains").bold()]),
					indicator: "green",
				});
			}
		});
    },

	sync_mailboxes(frm) {
        frappe.call({
			method: "mail.mail.doctype.mailbox.mailbox.sync_mailboxes",
			args: {
				agents: frm.doc.agent,
			},
			freeze: true,
			freeze_message: __("Creating Mail Agent Job..."),
			callback: () => {
				frappe.show_alert({
					message: __("{0} job has been created.", [__("Sync Mailboxes").bold()]),
					indicator: "green",
				});
			}
		});
    },

	sync_mail_aliases(frm) {
        frappe.call({
			method: "mail.mail.doctype.mail_alias.mail_alias.sync_mail_aliases",
			args: {
				agents: frm.doc.agent,
			},
			freeze: true,
			freeze_message: __("Creating Mail Agent Job..."),
			callback: () => {
				frappe.show_alert({
					message: __("{0} job has been created.", [__("Sync Mail Aliases").bold()]),
					indicator: "green",
				});
			}
		});
    },
});
