// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Mail Exchange'] = {
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

	refresh: (listview) => {
		set_account_options(listview)
	},
}

function set_account_options(listview) {
	const user_field = listview.page.fields_dict.user
	if (!user_field) return

	const user = user_field ? user_field.get_value() : null
	if (!user) return

	frappe.call({
		method: 'mail.jmap.get_user_accounts',
		args: {
			user: user,
		},
		callback: (r) => {
			const account_field = listview.page.fields_dict.account
			if (!account_field) return

			const options = r.message
			options.unshift('')
			account_field.df.options = options
			account_field.set_options()
		},
	})
}
