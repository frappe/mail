// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Address Book'] = {
	refresh: (listview) => {
		add_bulk_delete_button_to_actions(listview)
	},
}

function add_bulk_delete_button_to_actions(listview) {
	listview.page.add_actions_menu_item(__('Bulk Delete'), () => {
		const count = listview.get_checked_items().length

		frappe.confirm(
			__('Delete {0} {1} permanently?', [count, count === 1 ? 'item' : 'items']),
			() => {
				frappe.call({
					method: 'mail.client.doctype.address_book.address_book.bulk_delete',
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
