// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Settings", {
	refresh(frm) {
        frm.trigger("set_queries");
	},

    test_rabbitmq_connection(frm) {
		frappe.call({
			method: "test_rabbitmq_connection",
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Testing RabbitMQ Connection..."),
		});
	},

    set_queries(frm) {
        frm.set_query("postmaster", () => ({
            query: "mail.mail.doctype.mail_settings.mail_settings.get_postmaster",
            filters: {
                enabled: 1,
                role: "Postmaster",
            },
        }));
    },
});
