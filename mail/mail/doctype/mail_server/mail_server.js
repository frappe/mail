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
			__('Generate Config'),
			() => {
				frm.trigger('generate_config')
			},
			__('Actions'),
		)

		if (frm.doc.enabled && !frm.is_dirty()) {
			frm.add_custom_button(
				__('Reload Configuration'),
				() => {
					frm.trigger('reload_config')
				},
				__('Actions'),
			)
		}

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
				__('Install Docker (Playbook)'),
				() => {
					frm.trigger('install_docker')
				},
				__('Actions'),
			)
		}
	},

	generate_config(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'generate_config',
			freeze: true,
			freeze_message: __('Generating Config...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	reload_config(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'reload_config',
			freeze: true,
			freeze_message: __('Reloading Configuration...'),
			callback: (r) => {
				if (!r.exc) {
					frappe.show_alert(__('Configuration reloaded.'), 5)
					frm.refresh()
				}
			},
		})
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
})

frappe.ui.form.on('Mail Server ACME Provider', {
	acme_providers_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn]

		if (frm.doc.hostname) {
			row.directory_id = frm.doc.hostname.replaceAll('.', '-')
			row.domains = frm.doc.hostname
			row.contact = 'postmaster@' + frm.doc.hostname
		}
		if (frm.doc.acme_providers.length < 2) {
			row.default = 1
		}
		row.challenge = 'TLS-ALPN-01'
		row.directory = 'https://acme-v02.api.letsencrypt.org/directory'
		row.renew_before = 30
		refresh_field('acme_providers')
	},
})
