// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Mail Queue'] = {
	refresh: (listview) => {
		if (frappe.user_roles.includes('System Manager')) {
			add_bulk_retry_button_to_actions(listview)
			set_account_options(listview)
		}
	},

	get_indicator: (doc) => {
		const status_colors = {
			Queued: 'blue',
			Pending: 'orange',
			Failed: 'red',
			Drafted: 'grey',
			'Failed to Draft': 'red',
			Submitted: 'green',
			'Failed to Submit': 'red',
		}
		return [__(doc.status), status_colors[doc.status] || 'darkgrey', 'status,=,' + doc.status]
	},
}

function add_bulk_retry_button_to_actions(listview) {
	listview.page.add_actions_menu_item(__('Retry'), () => {
		frappe.call({
			method: 'mail.client.doctype.mail_queue.mail_queue.bulk_retry',
			args: {
				names: listview.get_checked_items(true),
			},
			callback: (r) => {
				if (!r.exc) {
					listview.refresh()
				}
			},
		})
	})
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
