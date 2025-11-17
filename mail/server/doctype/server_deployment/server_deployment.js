// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Server Deployment', {
	setup(frm) {
		frm.trigger('set_queries')
	},

	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.disable_save()
			frm.trigger('add_actions')
		}
	},

	set_queries(frm) {
		frm.set_query('config', () => ({
			filters: {
				server: frm.doc.server,
			},
		}))
	},

	add_actions(frm) {
		if (!frappe.user_roles.includes('System Manager')) return

		if (frm.doc.status === 'Success') {
			frm.add_custom_button(
				__('Filebeat Stream Setup (FC)'),
				() => frm.trigger('fc_filebeat_stream_setup'),
				__('Actions'),
			)

			frm.add_custom_button(
				__('Post Deployment SSL Setup (FC)'),
				() => frm.trigger('fc_post_deploy_ssl_setup'),
				__('Actions'),
			)
		}

		if (frm.doc.status === 'Failed') {
			frm.add_custom_button(__('Retry'), () => frm.trigger('retry'), __('Actions'))
		}
	},

	fc_filebeat_stream_setup(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'fc_filebeat_stream_setup',
			freeze: true,
			freeze_message: __('Setting up Filebeat Stream...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	fc_post_deploy_ssl_setup(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __('Post Deployment SSL Setup (FC)'),
			size: 'small',
			fields: [
				{
					fieldname: 'contact_email',
					fieldtype: 'Data',
					label: __('Contact Email'),
					reqd: 1,
				},
			],
			primary_action_label: __('Setup SSL'),
			primary_action: (data) => {
				const contact_email = data.contact_email
				if (!contact_email) {
					frappe.msgprint(__('Please enter a contact email'))
					return
				}

				frappe.call({
					doc: frm.doc,
					method: 'fc_post_deploy_ssl_setup',
					args: {
						contact_email: contact_email,
					},
					freeze: true,
					freeze_message: __('Setting up SSL...'),
					callback: (r) => {
						if (!r.exc) {
							frm.refresh()
							dialog.hide()
						}
					},
				})
			},
		})

		dialog.show()
	},

	retry(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'retry',
			freeze: true,
			freeze_message: __('Retrying...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
