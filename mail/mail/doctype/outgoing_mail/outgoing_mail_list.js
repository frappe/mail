// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Outgoing Mail"] = {
	get_indicator: function (doc) {
		const status_colors = {
			"Draft": "grey",
			"Queued": "blue",
			"Transferring": "yellow",
			"Failed": "red",
			"Transferred": "purple",
			"Partially Sent": "orange",
			"Sent": "green",
			"Cancelled": "red",
		};
		return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
	},
};