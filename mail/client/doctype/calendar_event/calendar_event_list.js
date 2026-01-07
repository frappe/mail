// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Calendar Event'] = {
	get_indicator: (doc) => {
		const status_colors = {
			Tentative: 'blue',
			Confirmed: 'green',
			Cancelled: 'red',
		}
		return [__(doc.status), status_colors[doc.status] || 'darkgrey', 'status,=,' + doc.status]
	},
}
