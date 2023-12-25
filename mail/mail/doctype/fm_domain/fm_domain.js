// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("FM Domain", {
	refresh(frm) {
        frm.trigger("set_domain_owner");
        frm.trigger("add_custom_buttons");
	},

    set_domain_owner(frm) {
        if (frm.doc.__islocal && !frm.doc.domain_owner && frappe.session.user) {
            frm.set_value("domain_owner", frappe.session.user);
        }
    },

    add_custom_buttons(frm) {
        frm.add_custom_button(__("Regenerate"), () => {
            frappe.confirm(
                __("Are you certain you wish to proceed?"),
                () => frm.trigger("generate_dns_records")
            )
        }, __("DNS Records"));
        frm.add_custom_button(__("Verify"), () => {
            frm.trigger("verify_dns_records");
        }, __("DNS Records"));
    },

    generate_dns_records(frm) {
        frappe.call({
            doc: frm.doc,
            method: "generate_dns_records",
            args: {
                save: true,
            },
            freeze: true,
            freeze_message: __("Generating DNS Records..."),
            callback: (r) => {
                if (!r.exc) {
                    frm.refresh();
                }
            }
        });
    },

    verify_dns_records(frm) {
        frappe.call({
            doc: frm.doc,
            method: "verify_dns_records",
            args: {
                save: true,
            },
            freeze: true,
            freeze_message: __("Verifying DNS Records..."),
            callback: (r) => {
                if (!r.exc) {
                    frm.refresh();
                }
            }
        });
    },
});
