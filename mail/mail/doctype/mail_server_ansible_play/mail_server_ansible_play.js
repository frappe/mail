// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Server Ansible Play', {
	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.disable_save()
			frm.trigger('add_actions')
		}

		frappe.realtime.on('ansible_play_progress', (data) => {
			if (data.progress && data.play === frm.doc.name) {
				const progress_title = __('Ansible Play Progress')
				frm.dashboard.show_progress(
					progress_title,
					(data.progress / data.total) * 100,
					`Ansible Play Progress (${data.progress} tasks completed out of ${data.total})`,
				)
				if (data.progress === data.total) {
					frm.dashboard.hide_progress(progress_title)
				}
			}
		})
	},

	add_actions(frm) {
		if (!frappe.user_roles.includes('System Manager')) return

		if (frm.doc.status === 'Failed') {
			frm.add_custom_button(__('Retry'), () => frm.trigger('retry'), __('Actions'))
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
})
