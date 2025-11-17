// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Queue', {
	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.disable_save()
			frm.trigger('add_comments')
			frm.trigger('add_actions')
		}
	},

	add_comments(frm) {
		if (
			!frm.doc.__islocal &&
			['Failed to Draft', 'Failed to Submit'].includes(frm.doc.status) &&
			frm.doc.error_message
		) {
			frm.dashboard.add_comment(__(frm.doc.error_message), 'red', true)
		}
	},

	add_actions(frm) {
		if (!frappe.user_roles.includes('System Manager')) return

		if (['Failed', 'Failed to Draft', 'Failed to Submit'].includes(frm.doc.status)) {
			frm.add_custom_button(__('Retry'), () => frm.trigger('retry'), __('Actions'))
		}

		if (
			frm.doc.blob_id &&
			!frm.doc.message &&
			(frm.doc.save_as_draft || !frm.doc.destroy_after_submission)
		) {
			frm.add_custom_button(
				__('Load MIME Message'),
				() => frm.trigger('get_mime_message'),
				__('Actions'),
			)
		}
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

	get_mime_message(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'get_mime_message',
			freeze: true,
			freeze_message: __('Loading MIME Message...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
