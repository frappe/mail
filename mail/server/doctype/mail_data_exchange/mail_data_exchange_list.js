// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Mail Data Exchange'] = {
	get_indicator: (doc) => {
		const status_colors = {
			Draft: 'grey',
			Queued: 'blue',
			'In Progress': 'orange',
			Completed: 'green',
			Failed: 'red',
			Cancelled: 'red',
		}
		return [__(doc.status), status_colors[doc.status] || 'darkgrey', 'status,=,' + doc.status]
	},
}
