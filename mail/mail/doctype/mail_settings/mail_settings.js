// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Settings", {
    refresh(frm) {
        frm.trigger("set_queries");
        frm.trigger("add_comments");
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

    add_comments(frm) {
        if (frm.doc.root_domain_name && (!frm.doc.dns_provider || !frm.doc.dns_provider_token)) {
            let bold_root_domain_name = `<b>${frm.doc.root_domain_name}</b>`;
            let dns_record_list_link = `<a href="/app/dns-record">${__("DNS Records")}</a>`;
            let msg = __(
                "DNS provider or token not configured. Please manually add the {0} to the DNS provider for the domain {1} to ensure proper email authentication.", [dns_record_list_link, bold_root_domain_name]
            );
            frm.dashboard.add_comment(msg, "yellow", true);
        }
    }
});
