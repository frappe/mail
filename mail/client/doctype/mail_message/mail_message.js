// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Mail Message', {
	refresh(frm) {
		frm.disable_save()

		if (!frm.doc.__islocal) {
			if (!frm.doc.draft) {
				frm.trigger('add_seen_flagged_buttons')
			}

			if (!frm.doc.draft) {
				frm.trigger('add_reply_forward_buttons')
				frm.trigger('add_move_buttons')
				frm.trigger('add_to_buttons')
				frm.trigger('add_remove_from_buttons')
			} else {
				frm.trigger('add_draft_submit_buttons')
			}

			frm.trigger('add_actions')
		}
	},

	user(frm) {
		if (frm.doc.user) {
			frappe.call({
				method: 'mail.jmap.get_user_accounts',
				args: {
					user: frm.doc.user,
				},
				callback: (r) => {
					if (r.message) {
						frm.set_df_property('account', 'options', r.message)
						frm.refresh_field('account')
					}
				},
			})
		} else {
			frm.set_df_property('account', 'options', [])
			frm.refresh_field('account')
		}
	},

	add_seen_flagged_buttons(frm) {
		const add_toggle_button = (field, method, labels, freeze_messages) => {
			const current = frm.doc[field]
			const label = current ? __(labels[1]) : __(labels[0])
			const freeze_message = current ? __(freeze_messages[1]) : __(freeze_messages[0])

			frm.add_custom_button(label, () => {
				frappe.call({
					doc: frm.doc,
					method,
					args: {
						[field]: !current,
					},
					freeze: true,
					freeze_message,
					callback: (r) => {
						if (!r.exc) {
							frm.refresh()
						}
					},
				})
			})
		}

		add_toggle_button(
			'seen',
			'set_seen',
			['Seen', 'Unseen'],
			['Marking as Seen...', 'Marking as Unseen...'],
		)

		add_toggle_button(
			'flagged',
			'set_flagged',
			['Flag', 'Unflag'],
			['Flagging...', 'Unflagging...'],
		)
	},

	add_reply_forward_buttons(frm) {
		frm.add_custom_button(
			__('Reply'),
			() => {
				frappe.model.open_mapped_doc({
					method: 'mail.client.doctype.mail_message.mail_message.reply',
					frm: frm,
					freeze: true,
					freeze_message: __('Loading...'),
				})
			},
			__('Reply / Forward'),
		)

		frm.add_custom_button(
			__('Reply All'),
			() => {
				frappe.model.open_mapped_doc({
					method: 'mail.client.doctype.mail_message.mail_message.reply_all',
					frm: frm,
					freeze: true,
					freeze_message: __('Loading...'),
				})
			},
			__('Reply / Forward'),
		)

		frm.add_custom_button(
			__('Forward'),
			() => {
				frappe.model.open_mapped_doc({
					method: 'mail.client.doctype.mail_message.mail_message.forward',
					frm: frm,
					freeze: true,
					freeze_message: __('Loading...'),
				})
			},
			__('Reply / Forward'),
		)
	},

	add_move_buttons(frm) {
		frappe.call({
			method: 'mail.jmap.get_mailboxes_for_account',
			args: {
				account: frm.doc.account,
			},
			freeze: true,
			freeze_message: __('Loading Mailboxes...'),
			callback: (r) => {
				if (!r.exc) {
					const mailboxes = r.message || []
					if (mailboxes.length === 0) return

					mailboxes.forEach((mailbox) => {
						if (mailbox.role === 'drafts') return

						frm.add_custom_button(
							__('Move to ' + mailbox._name),
							() => frm.events.move_to_mailbox(frm, mailbox.id),
							__('Move'),
						)
					})
				}
			},
		})
	},

	add_to_buttons(frm) {
		frappe.call({
			method: 'mail.jmap.get_mailboxes_for_account',
			args: {
				account: frm.doc.account,
			},
			freeze: true,
			freeze_message: __('Loading Mailboxes...'),
			callback: (r) => {
				if (!r.exc) {
					const mailboxes = r.message || []
					if (mailboxes.length === 0) return

					const current_mailboxes = frm.doc.mailboxes || []

					mailboxes.forEach((mailbox) => {
						const exists_in_current = current_mailboxes.some(
							(m) => m.mailbox_id === mailbox.id,
						)

						if (exists_in_current || mailbox.role === 'drafts') return

						frm.add_custom_button(
							__('Add to ' + mailbox._name),
							() => frm.events.add_to_mailbox(frm, mailbox.id),
							__('Add'),
						)
					})
				}
			},
		})
	},

	add_remove_from_buttons(frm) {
		const current_mailboxes = frm.doc.mailboxes || []
		if (current_mailboxes.length <= 1) return

		current_mailboxes.forEach((mailbox) => {
			if (mailbox.role === 'drafts') return

			frm.add_custom_button(
				__('Remove from ' + mailbox.mailbox_name),
				() => frm.events.remove_from_mailbox(frm, mailbox.mailbox_id),
				__('Remove'),
			)
		})
	},

	add_draft_submit_buttons(frm) {
		const add_button = (label, method, freeze_message) => {
			frm.add_custom_button(__(label), () => {
				frappe.call({
					doc: frm.doc,
					method: method,
					freeze: true,
					freeze_message: __(freeze_message),
					callback: (r) => {
						if (!r.exc) {
							frappe.set_route('List', 'Mail Message')
						}
					},
				})
			})
		}

		add_button('Save Draft', 'save_draft', 'Saving Draft...')
		add_button('Submit', 'submit', 'Submitting...')
	},

	add_actions(frm) {
		if (frm.doc.has_attachment) {
			frm.add_custom_button(
				__('Load Attachments'),
				() => frm.trigger('load_attachments'),
				__('Actions'),
			)
		}

		if (!frm.doc.message) {
			frm.add_custom_button(
				__('Load MIME Message'),
				() => frm.trigger('get_mime_message'),
				__('Actions'),
			)
		}
	},

	move_to_mailbox(frm, mailbox_id) {
		frappe.call({
			doc: frm.doc,
			method: 'move_to_mailbox',
			freeze: true,
			freeze_message: __('Moving to Mailbox...'),
			args: {
				mailbox_id: mailbox_id,
			},
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	add_to_mailbox(frm, mailbox_id) {
		frappe.call({
			doc: frm.doc,
			method: 'add_to_mailbox',
			freeze: true,
			freeze_message: __('Adding to Mailbox...'),
			args: {
				mailbox_id: mailbox_id,
			},
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	remove_from_mailbox(frm, mailbox_id) {
		frappe.call({
			doc: frm.doc,
			method: 'remove_from_mailbox',
			freeze: true,
			freeze_message: __('Removing from Mailbox...'),
			args: {
				mailbox_id: mailbox_id,
			},
			callback: (r) => {
				if (!r.exc) {
					frm.refresh()
				}
			},
		})
	},

	load_attachments(frm) {
		frappe.call({
			doc: frm.doc,
			method: 'load_attachments',
			args: {
				include_inline: true,
				include_regular: true,
			},
			freeze: true,
			freeze_message: __('Loading Attachments...'),
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
