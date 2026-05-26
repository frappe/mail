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
				frm.trigger('add_mailbox_buttons')
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

	call_doc_method(frm, method, args, freeze_message, callback) {
		frappe.call({
			doc: frm.doc,
			method,
			args: args || {},
			freeze: true,
			freeze_message: __(freeze_message),
			callback:
				callback ||
				((r) => {
					if (!r.exc) frm.refresh()
				}),
		})
	},

	add_seen_flagged_buttons(frm) {
		const add_toggle_button = (field, method, labels, freeze_messages) => {
			const current = frm.doc[field]
			const label = current ? __(labels[1]) : __(labels[0])
			const freeze_message = current ? __(freeze_messages[1]) : __(freeze_messages[0])

			frm.add_custom_button(label, () => {
				frm.events.call_doc_method(frm, method, { [field]: !current }, freeze_message)
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
		const add_mapped_button = (label, method) => {
			frm.add_custom_button(
				__(label),
				() => {
					frappe.model.open_mapped_doc({
						method,
						frm: frm,
						freeze: true,
						freeze_message: __('Loading...'),
					})
				},
				__('Reply / Forward'),
			)
		}

		add_mapped_button('Reply', 'mail.client.doctype.mail_message.mail_message.reply')
		add_mapped_button('Reply All', 'mail.client.doctype.mail_message.mail_message.reply_all')
		add_mapped_button('Forward', 'mail.client.doctype.mail_message.mail_message.forward')
	},

	add_mailbox_buttons(frm) {
		const current_mailboxes = frm.doc.mailboxes || []

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

						const already_in_mailbox = current_mailboxes.some(
							(m) => m.mailbox_id === mailbox.id,
						)
						if (!already_in_mailbox) {
							frm.add_custom_button(
								__('Add to ' + mailbox._name),
								() => frm.events.add_to_mailbox(frm, mailbox.id),
								__('Add'),
							)
						}
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
		const navigate_to_list = (r) => {
			if (!r.exc) frappe.set_route('List', 'Mail Message')
		}

		frm.add_custom_button(__('Save Draft'), () => {
			frm.events.call_doc_method(frm, 'save_draft', {}, 'Saving Draft...', navigate_to_list)
		})

		frm.add_custom_button(__('Submit'), () => {
			frm.events.call_doc_method(frm, 'submit', {}, 'Submitting...', navigate_to_list)
		})
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
		frm.events.call_doc_method(frm, 'move_to_mailbox', { mailbox_id }, 'Moving to Mailbox...')
	},

	add_to_mailbox(frm, mailbox_id) {
		frm.events.call_doc_method(frm, 'add_to_mailbox', { mailbox_id }, 'Adding to Mailbox...')
	},

	remove_from_mailbox(frm, mailbox_id) {
		frm.events.call_doc_method(
			frm,
			'remove_from_mailbox',
			{ mailbox_id },
			'Removing from Mailbox...',
		)
	},

	load_attachments(frm) {
		frm.events.call_doc_method(
			frm,
			'load_attachments',
			{ include_inline: true, include_regular: true },
			'Loading Attachments...',
		)
	},

	get_mime_message(frm) {
		frm.events.call_doc_method(frm, 'get_mime_message', {}, 'Loading MIME Message...')
	},
})
