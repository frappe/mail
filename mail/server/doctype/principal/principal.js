// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Principal', {
	refresh(frm) {
		frm.trigger('add_actions')
		frm.trigger('add_comments')
	},

	add_actions(frm) {
		if (!frm.doc.__islocal) {
			if (frm.doc.type == 'Domain') {
				frm.add_custom_button(
					__('Verify DNS Records'),
					() => {
						frm.trigger('verify_dns_records')
					},
					__('Actions'),
				)

				frm.add_custom_button(
					__('Refresh DNS Records'),
					() => {
						frappe.confirm(
							__(
								"Are you sure you want to refresh the DNS records? If there are any changes, you'll need to update the DNS settings with your DNS provider accordingly.",
							),
							() => frm.trigger('refresh_dns_records'),
						)
					},
					__('Actions'),
				)

				frm.add_custom_button(
					__('Rotate DKIM Keys'),
					() => {
						frappe.confirm(
							__(
								"Are you sure you want to rotate the DKIM keys? This will generate new keys for email signing and you'll need to update the DNS settings with your DNS provider accordingly. This may take some time to propagate across DNS servers. Emails sent during this period may fail DKIM verification.",
							),
							() => frm.trigger('rotate_dkim_keys'),
						)
					},
					__('Actions'),
				)
			} else if (frm.doc.type === 'Individual') {
				frm.add_custom_button(
					__('Sync JMAP Identities'),
					() => {
						frm.trigger('sync_jmap_identities')
					},
					__('Actions'),
				)
			}
		}
	},

	add_comments(frm) {
		if (frm.doc.type === 'Domain') {
			if (!frm.doc.is_verified) {
				const bold_domain_name = `<b>${frm.doc._name}</b>`
				const msg = __(
					'DNS records for the domain {0} are not verified. Please ensure that the DNS records are correctly configured with your DNS provider to enable proper email authentication.',
					[bold_domain_name],
				)
				frm.dashboard.add_comment(msg, 'yellow', true)
			}
		}
	},

	verify_dns_records(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'verify_dns_records',
			args: {},
			freeze: true,
			freeze_message: __('Verifying DNS Records...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	refresh_dns_records(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'refresh_dns_records',
			args: {},
			freeze: true,
			freeze_message: __('Refreshing DNS Records...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	rotate_dkim_keys(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'rotate_dkim_keys',
			args: {},
			freeze: true,
			freeze_message: __('Rotating DKIM Keys...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	sync_jmap_identities(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'sync_jmap_identities',
			args: {},
			freeze: true,
			freeze_message: __('Syncing JMAP Identities...'),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},
})
