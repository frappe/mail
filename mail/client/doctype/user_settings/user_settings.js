// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('User Settings', {
	refresh(frm) {
		frm.trigger('add_actions')
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		if (frappe.user_roles.includes('Administrator') && frm.doc.app_password) {
			frm.add_custom_button(__('Show App Password'), () => {
				frm.trigger('show_app_password')
			})
		}

		const actions = [
			{
				condition: frm.doc.has_cached_jmap_connection,
				label: __('JMAP Connection'),
				method: 'clear_cached_jmap_connection',
				message: __('Clearing Cached JMAP Connection...'),
			},
			{
				condition: frm.doc.has_cached_jmap_identities,
				label: __('JMAP Identities'),
				method: 'clear_cached_jmap_identities',
				message: __('Clearing Cached JMAP Identities...'),
			},
			{
				condition: frm.doc.has_cached_jmap_mailboxes,
				label: __('JMAP Mailboxes'),
				method: 'clear_cached_jmap_mailboxes',
				message: __('Clearing Cached JMAP Mailboxes...'),
			},
			{
				condition: frm.doc.total_cached_blobs,
				label: __('Blobs'),
				method: 'clear_cached_blobs',
				message: __('Clearing Cached Blobs...'),
			},
			{
				condition: frm.doc.total_cached_mail_messages,
				label: __('Mail Messages'),
				method: 'clear_cached_mail_messages',
				message: __('Clearing Cached Mail Messages...'),
			},
			{
				condition: frm.doc.total_cached_contact_cards,
				label: __('Contact Cards'),
				method: 'clear_cached_contact_cards',
				message: __('Clearing Cached Contact Cards...'),
			},
		]

		actions.forEach((action) => {
			if (!action.condition) return

			frm.add_custom_button(
				action.label,
				() => frm.trigger('run_cache_clear_action', action),
				__('Clear Cache'),
			)
		})
	},

	show_app_password(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'show_app_password',
			freeze: true,
			freeze_message: __('Getting Password...'),
			callback: (r) => {
				if (!r.exc) {
					frappe.msgprint(r.message)
				}
			},
		})
	},

	run_cache_clear_action(frm, action) {
		frappe.call({
			doc: frm.doc,
			method: action.method,
			freeze: true,
			freeze_message: action.message,
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
