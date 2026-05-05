// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Server', {
	setup(frm) {
		frm.trigger('set_queries')
	},

	refresh(frm) {
		frm.trigger('add_actions')
	},

	set_queries(frm) {
		frm.set_query('cluster', () => ({
			filters: {
				enabled: 1,
			},
		}))
	},

	add_actions(frm) {
		if (frm.doc.__islocal) return

		if (!frappe.user_roles.includes('System Manager')) return

		frm.add_custom_button(
			__('Verify SSH Connection'),
			() => {
				frm.trigger('verify_ssh_connection')
			},
			__('Actions'),
		)

		if (frm.doc.ssh_verified) {
			frm.add_custom_button(
				__('Install Ansible (Job)'),
				() => {
					frm.trigger('install_ansible')
				},
				__('Actions'),
			)

			frm.add_custom_button(
				__('Install Docker (Ansible Play)'),
				() => {
					frm.trigger('install_docker')
				},
				__('Actions'),
			)

			frm.add_custom_button(
				__('Install Stalwart (Deployment)'),
				() => {
					frappe.confirm(__('Are you sure you want to proceed?'), () =>
						frm.trigger('install_stalwart'),
					)
				},
				__('Actions'),
			)
		}
	},

	verify_ssh_connection(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'verify_ssh_connection',
			freeze: true,
			freeze_message: __('Verifying SSH Connection...'),
		})
	},

	install_ansible(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'install_ansible',
			freeze: true,
			freeze_message: __('Installing Ansible...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	install_docker(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'install_docker',
			freeze: true,
			freeze_message: __('Installing Docker...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	install_stalwart(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'install_stalwart',
			freeze: true,
			freeze_message: __('Installing Stalwart...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
