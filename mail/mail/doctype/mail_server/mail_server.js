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
			__('Generate Mail Server Config'),
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
	},

	generate_config(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'generate_config',
			freeze: true,
			freeze_message: __('Generating Mail Server Config...'),
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
			freeze_message: __('Reloading Server Configuration...'),
			callback: (r) => {
				if (!r.exc) {
					frappe.show_alert(__('Server Configuration reloaded.'), 5)
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
