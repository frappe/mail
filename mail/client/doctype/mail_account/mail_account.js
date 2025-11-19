// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Account', {
	setup(frm) {
		frm.trigger('set_queries')
	},

	refresh(frm) {
		frm.trigger('add_show_app_password')
		frm.trigger('add_actions')
	},

	set_queries(frm) {
		frm.set_query('domain_name', () => ({
			filters: {
				enabled: 1,
				is_verified: 1,
			},
		}))

		frm.set_query('user', () => ({
			query: 'mail.utils.query.get_users_with_mail_user_role',
			filters: {
				enabled: 1,
				role: 'Mail User',
			},
		}))
	},

	add_show_app_password(frm) {
		if (frm.doc.__islocal) return

		if (frm.doc.app_password) {
			frm.add_custom_button(__('Show App Password'), () =>
				frm.trigger('get_account_app_password'),
			)
		}
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		if (frappe.user_roles.includes('System Manager')) {
			frm.add_custom_button(
				__('Sync JMAP Identities'),
				() => frm.trigger('sync_jmap_identities'),
				__('Actions'),
			)

			frm.add_custom_button(
				__('Invalidate JMAP Cache'),
				() => {
					frappe.confirm(
						__(
							'Are you sure you want to invalidate the JMAP cache? This action will permanently remove all cached connections, mailboxes, identities, and address books data.',
						),
						() => frm.trigger('invalidate_jmap_cache'),
					)
				},
				__('Actions'),
			)
		}

		if (frm.doc.enabled && frappe.user_roles.includes('Mail Admin')) {
			frm.add_custom_button(__('Set Quota'), () => frm.trigger('set_quota'), __('Actions'))
		}

		frm.add_custom_button(
			__('Set Vacation Response'),
			() => frm.trigger('set_vacation_response'),
			__('Actions'),
		)

		frm.add_custom_button(
			__('Re-generate App Password'),
			() => frm.trigger('regenerate_app_password'),
			__('Actions'),
		)
	},

	get_account_app_password(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'get_account_app_password',
			freeze: true,
			freeze_message: __('Getting App Password...'),
			callback: (r) => {
				if (!r.exc) {
					frappe.msgprint(r.message)
				}
			},
		})
	},

	sync_jmap_identities(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'sync_jmap_identities',
			freeze: true,
			freeze_message: __('Syncing JMAP Identities...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	invalidate_jmap_cache(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'invalidate_jmap_cache',
			freeze: true,
			freeze_message: __('Invalidating JMAP Cache...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	set_quota(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __('Set Quota'),
			size: 'small',
			fields: [
				{
					fieldname: 'quota',
					fieldtype: 'Float',
					label: __('Quota (in GB)'),
					description: __('<code><b>0</b></code> means no quota restriction.'),
					reqd: 1,
					precision: 5,
					default: frm.doc.disk_quota || 0,
				},
			],
			primary_action_label: __('Set Quota'),
			primary_action: (data) => {
				const quota = data.quota
				if (quota < 0) {
					frappe.msgprint(__('Quota cannot be negative.'))
					return
				}

				frappe.call({
					doc: frm.doc,
					method: 'set_quota',
					args: {
						quota: Math.round(quota * 1024 * 1024 * 1024),
					},
					freeze: true,
					freeze_message: __('Setting Quota...'),
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

	set_vacation_response(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __('Set Vacation Response'),
			size: 'large',
			fields: [
				{
					fieldname: 'enabled',
					fieldtype: 'Check',
					label: __('Enabled'),
					default: frm.doc.vacation_response_enabled || 0,
				},
				{
					fieldtype: 'Section Break',
				},
				{
					fieldname: 'from_date',
					fieldtype: 'Datetime',
					label: __('From Date'),
					default: frm.doc.vacation_from_date || '',
					mandatory_depends_on: 'enabled',
				},
				{
					fieldname: 'to_date',
					fieldtype: 'Datetime',
					label: __('To Date'),
					default: frm.doc.vacation_to_date || '',
					mandatory_depends_on: 'enabled',
				},
				{
					fieldtype: 'Column Break',
				},
				{
					fieldname: 'subject',
					fieldtype: 'Data',
					label: __('Subject'),
					default: frm.doc.vacation_response_subject || '',
				},
				{
					fieldtype: 'Section Break',
				},
				{
					fieldname: 'text_body',
					fieldtype: 'Code',
					label: __('Text'),
					default: frm.doc.vacation_response_text_body || '',
				},
				{
					fieldname: 'html_body',
					fieldtype: 'Text Editor',
					label: __('HTML'),
					options: 'text/html',
					default: frm.doc.vacation_response_html_body || '',
				},
			],
			primary_action_label: __('Set Vacation Response'),
			primary_action: (data) => {
				frappe.call({
					doc: frm.doc,
					method: 'set_vacation_response',
					args: {
						enabled: data.enabled,
						from_date: data.from_date,
						to_date: data.to_date,
						subject: data.subject,
						text_body: data.text_body,
						html_body: data.html_body,
					},
					freeze: true,
					freeze_message: __('Setting Vacation Response...'),
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

	regenerate_app_password(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __('Regenerate App Password'),
			size: 'small',
			fields: [
				{
					fieldname: 'account_password',
					fieldtype: 'Password',
					label: __('Login/Account Password'),
					description: __(
						'Your main login/account password is required to regenerate the app password.',
					),
					reqd: 1,
				},
			],
			primary_action_label: __('Regenerate'),
			primary_action: (data) => {
				frappe.call({
					doc: frm.doc,
					method: 'regenerate_app_password',
					args: {
						account_password: data.account_password,
					},
					freeze: true,
					freeze_message: __('Regenerating App Password...'),
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
})
