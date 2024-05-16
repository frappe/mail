// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Settings", {
	refresh(frm) {
        frm.trigger("set_queries");
	},

    set_queries(frm) {
        frm.set_query("postmaster", () => {
            return {
                query: "mail.mail.doctype.mail_settings.mail_settings.get_postmaster",
                filters: {
                    enabled: 1,
                    role: "Postmaster",
                },
            };
        });
    },
});
