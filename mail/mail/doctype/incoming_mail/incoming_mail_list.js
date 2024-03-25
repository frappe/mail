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
};