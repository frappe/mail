// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["FM Outgoing Email"] = {
	get_indicator: function (doc) {
		const status_colors = {
			"Queued": "blue",
			"Sent": "green",
			"Failed": "red",
		};
		return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
	},
};