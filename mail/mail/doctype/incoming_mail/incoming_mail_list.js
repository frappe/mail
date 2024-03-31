// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Incoming Mail"] = {
	get_indicator: function (doc) {
		const status_colors = {
			"Draft": "grey",
			"Delivered": "green",
			"Cancelled": "red",
		};
		return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
	},

	refresh: function(listview) {
        listview.page.add_inner_button("Refresh", function() {
            get_incoming_mails(listview);
        });;
    },
};

function get_incoming_mails(listview) {
	frappe.call({
		method: "mail.mail.doctype.incoming_mail.incoming_mail.get_incoming_mails",
		freeze: true,
		freeze_message: __("Receiving Mails..."),
		callback: function() {
			frappe.show_alert({
				message: __("Get Incoming Mails Job has been started in the background."),
				indicator: "green",
			});
		}
	});
}