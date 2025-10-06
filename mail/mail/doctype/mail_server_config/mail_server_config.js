// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Server Config', {
	refresh(frm) {
		frm.trigger('add_actions')
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		if (frappe.user_roles.includes('System Manager')) {
			frm.add_custom_button(
				__('Deploy'),
				() => {
					frappe.confirm(__('Are you sure you want to proceed?'), () =>
						frm.trigger('deploy'),
					)
				},
				__('Actions'),
			)
			frm.add_custom_button(
				__('Update config.toml'),
				() => {
					frappe.confirm(__('Are you sure you want to proceed?'), () =>
						frm.trigger('update_config_on_server'),
					)
				},
				__('Actions'),
			)
		}
	},

	deploy(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'deploy',
			freeze: true,
			freeze_message: __('Deploying Configuration...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	update_config_on_server(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'update_config_on_server',
			freeze: true,
			freeze_message: __('Updating Configuration...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
