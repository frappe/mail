// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Message Queue', {
	refresh(frm) {
		frm.trigger('add_actions')
	},

	add_actions(frm) {
		if (!frappe.user_roles.includes('System Manager')) return

		frm.page.set_primary_action('Retry', () => frm.trigger('retry_delivery'))
		frm.page.set_secondary_action('Cancel', () => frm.trigger('cancel_delivery'))
	},

	retry_delivery(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'retry_delivery',
			freeze: true,
			freeze_message: __('Retrying Delivery...'),
			callback: () => {
				frm.reload_doc()
			},
		})
	},

	cancel_delivery(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __('Cancel Delivery'),
			size: 'large',
			fields: [
				{
					fieldname: 'recipients',
					fieldtype: 'Table',
					label: __('Recipients'),
					allow_bulk_edit: false,
					cannot_add_rows: true,
					cannot_delete_rows: true,
					data: [],
					fields: [
						{ fieldtype: 'Section Break' },
						{
							fieldname: 'email',
							fieldtype: 'Data',
							label: __('Email'),
							in_list_view: 1,
							read_only: 1,
						},
						{
							fieldname: 'domain_name',
							fieldtype: 'Data',
							label: __('Domain Name'),
							read_only: 1,
						},
						{ fieldtype: 'Column Break' },
						{
							fieldname: 'status',
							fieldtype: 'Data',
							label: __('Status'),
							in_list_view: 1,
							read_only: 1,
						},

						{
							fieldname: 'retry_num',
							fieldtype: 'Int',
							label: __('Retry Num'),
							in_list_view: 1,
							read_only: 1,
						},
						{ fieldtype: 'Section Break' },
						{
							fieldname: 'next_retry',
							fieldtype: 'Datetime',
							label: __('Next Retry'),
							in_list_view: 1,
							read_only: 1,
						},
						{
							fieldname: 'next_notify',
							fieldtype: 'Datetime',
							label: __('Next Notify'),
							read_only: 1,
						},
						{ fieldtype: 'Column Break' },
						{
							fieldname: 'expires',
							fieldtype: 'Datetime',
							label: __('Expires'),
							read_only: 1,
						},
						{ fieldtype: 'Section Break' },
						{
							fieldname: 'server_response',
							fieldtype: 'JSON',
							label: __('Server Response'),
							read_only: 1,
						},
					],
				},
			],
			primary_action_label: __('Cancel Delivery'),
			primary_action: () => {
				const data = {
					recipients: dialog.fields_dict.recipients.grid.get_selected_children(),
				}

				if (data.recipients && data.recipients.length > 0) {
					frappe.call({
						doc: frm.doc,
						method: 'cancel_delivery',
						args: {
							recipients: data.recipients.map((recipient) => recipient.email),
						},
						freeze: true,
						freeze_message: __('Cancelling Delivery...'),
						callback: () => {
							if (
								data.recipients.length ==
								dialog.fields_dict.recipients.df.data.length
							) {
								frappe.set_route('List', 'Message Queue', {
									cluster: frm.doc.cluster,
								})
							} else {
								frm.reload_doc()
							}
						},
					})

					dialog.hide()
				} else {
					frappe.msgprint(__('Please select recipients to cancel delivery.'))
				}
			},
		})

		frm.doc.recipients.forEach((recipient) => {
			if (recipient.status !== 'Permanent Failure') {
				dialog.fields_dict.recipients.df.data.push({
					email: recipient.email,
					domain_name: recipient.domain_name,
					status: recipient.status,
					retry_num: recipient.retry_num,
					next_retry: recipient.next_retry,
					next_notify: recipient.next_notify,
					expires: recipient.expires,
					server_response: recipient.server_response,
				})
			}
		})

		dialog.fields_dict.recipients.grid.refresh()
		dialog.show()
	},
})
