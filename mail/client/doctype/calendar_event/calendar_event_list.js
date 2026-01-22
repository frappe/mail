// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Calendar Event'] = {
	refresh: (listview) => {
		add_bulk_delete_button_to_actions(listview)
	},

	get_indicator: (doc) => {
		const status_colors = {
			Tentative: 'blue',
			Confirmed: 'green',
			Cancelled: 'red',
		}
		return [__(doc.status), status_colors[doc.status] || 'darkgrey', 'status,=,' + doc.status]
	},
}

function add_bulk_delete_button_to_actions(listview) {
	listview.page.add_actions_menu_item(__('Bulk Delete'), () => {
		const count = listview.get_checked_items().length

		frappe.confirm(
			__('Delete {0} {1} permanently?', [count, count === 1 ? 'item' : 'items']),
			() => {
				frappe.call({
					method: 'mail.client.doctype.calendar_event.calendar_event.bulk_delete',
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
