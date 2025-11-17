// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['JMAP Push Subscription'] = {
	get_indicator: (doc) => {
		const status_colors = {
			Active: 'green',
			Expired: 'red',
			'Failed to Verify': 'red',
			'Failed to Renew': 'red',
			'Failed to Subscribe': 'red',
			'Pending Verification': 'yellow',
		}
		return [__(doc.status), status_colors[doc.status], 'status,=,' + doc.status]
	},
}
