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
				frm.add_custom_button(__("Get Outgoing Mails Status"), () => {
					frm.trigger("get_outgoing_mails_status");
				}, __("Actions"));
			}

			if (frm.doc.incoming) {
				frm.add_custom_button(__("Get Incoming Mails"), () => {
					frm.trigger("get_incoming_mails");
				}, __("Actions"));
			}
		}
    },

	get_outgoing_mails_status(frm) {
		frappe.call({
			method: "mail.mail.doctype.outgoing_mail.outgoing_mail.get_outgoing_mails_status",
			args: {
				agents: frm.doc.agent,
			},
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

	get_incoming_mails(frm) {
        frappe.call({
			method: "mail.mail.doctype.incoming_mail.incoming_mail.get_incoming_mails",
			freeze: true,
			freeze_message: __("Creating Job..."),
			callback: () => {
				frappe.show_alert({
					message: __("{0} job has been created.", [__("Get Mails").bold()]),
					indicator: "green",
				});
			}
		});
    },
});
