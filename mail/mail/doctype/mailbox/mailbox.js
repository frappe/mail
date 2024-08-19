// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mailbox", {
	setup(frm) {
        frm.trigger("set_queries");
    },

	set_queries(frm) {
		frm.set_query("domain_name", () => ({
            query: "mail.mail.doctype.mailbox.mailbox.get_domain",
        }));

		frm.set_query("user", () => ({
            query: "mail.mail.doctype.mailbox.mailbox.get_user",
        }));
    },
});
