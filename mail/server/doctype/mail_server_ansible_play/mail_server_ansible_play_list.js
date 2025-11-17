// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Mail Server Ansible Play'] = {
	get_indicator: (doc) => {
		const status_colors = {
			Pending: 'orange',
			Running: 'yellow',
			Success: 'green',
			Failed: 'red',
		}
		return [__(doc.status), status_colors[doc.status] || 'darkgrey', 'status,=,' + doc.status]
	},
}
