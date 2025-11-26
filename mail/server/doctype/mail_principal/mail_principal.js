// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Principal', {
	refresh(frm) {
		frm.trigger('add_actions')
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
			}

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
})
