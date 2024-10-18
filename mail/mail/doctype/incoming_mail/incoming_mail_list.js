// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Incoming Mail"] = {
	refresh: (listview) => {
		listview.page.add_inner_button("Refresh", () => {
			get_incoming_mails(listview);
		});;
	},

	get_indicator: (doc) => {
		const status_colors = {
			"Draft": "grey",
			"Rejected": "red",
			"Accepted": "green",
			"Cancelled": "red",
		};
		return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
	},
};

function get_incoming_mails(listview) {
	frappe.call({
		method: "mail.mail.doctype.incoming_mail.incoming_mail.enqueue_get_incoming_mails",
		freeze: true,
		freeze_message: __("Creating Job..."),
		callback: () => {
			frappe.show_alert({
				message: __("{0} job has been created.", [__("Get Mails").bold()]),
				indicator: "green",
			});
		}
	});
}