// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings['Mail Server'] = {
	refresh: (listview) => {
		add_reload_config_button(listview)
	},
}

function add_reload_config_button(listview) {
	listview.page.add_actions_menu_item(__('Reload Configuration'), () => {
		frappe.call({
			method: 'mail.server.doctype.mail_server.mail_server.reload_servers_config',
			args: {
				servers: listview.get_checked_items(true),
			},
			freeze: true,
			freeze_message: __('Reloading Configuration...'),
			callback: (r) => {
				if (!r.exc) {
					listview.refresh()
				}
			},
		})
	})
}
