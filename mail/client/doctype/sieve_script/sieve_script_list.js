// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Sieve Script'] = {
	refresh: (listview) => {
		add_bulk_delete_button_to_actions(listview)
		set_account_options(listview)
	},
}

function add_bulk_delete_button_to_actions(listview) {
	listview.page.add_actions_menu_item(__('Bulk Delete'), () => {
		const count = listview.get_checked_items().length

		frappe.confirm(
			__('Delete {0} {1} permanently?', [count, count === 1 ? 'item' : 'items']),
			() => {
				frappe.call({
					method: 'mail.client.doctype.sieve_script.sieve_script.bulk_delete',
					args: {
						names: listview.get_checked_items(true),
					},
					callback: (r) => {
						if (!r.exc) {
							listview.refresh()
						}
					},
				})
			},
		)
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
