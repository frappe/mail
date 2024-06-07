// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Mail Agent Job"] = {
	get_indicator: (doc) => {
		const status_colors = {
			"Queued": "blue",
			"Running": "yellow",
			"Completed": "green",
			"Failed On Start": "orange",
			"Failed": "red",
			"Failed On End": "orange",
		};
		return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
	},
};