export * from './doctypes'

export interface User {
	name: string
	email: string
	full_name: string
	user_type: string

	username: string | null
	user_image: string | null
	api_key: string | null
	tenant: string | null
	user_settings?: string
	default_outgoing_email?: string
	color_scheme?: 'System Default' | 'Light Mode' | 'Dark Mode'
	group_messages_by?: 'None' | 'Day' | 'Month'
	show_reading_pane?: 0 | 1

	enabled: boolean
	is_mail_user: boolean
	is_mail_admin: boolean
	is_tenant_owner?: boolean
	is_system_manager: boolean

	tenant_name?: string
	mailboxes: { id: string; name: string; role: string }[]
}

export interface UserResource {
	data: User
	promise: Promise<User>
}

export interface Recipient {
	type: 'To' | 'Cc' | 'Bcc'
	email: string
	display_name: string | null
}

export interface Mailbox {
	mailbox: string
	mailbox_id: string
	mailbox_name: string
}
export interface Attachment {
	filename: string
	blob_id: string
	type: string
	size: string
	file_url: string | null
	disposition: string
	cid?: string
}

export interface Mail {
	name: string
	message_id: string
	id: string
	from_name: string
	from_email: string
	subject: string
	html_body: string
	text_body: string
	received_at: string
	draft: 0 | 1
	flagged: 0 | 1
	seen: 0 | 1
	junk: 0 | 1
	mailboxes: Mailbox[]
	recipients: Recipient[]
	groupedRecipients: {
		to: string[]
		cc: string[]
		bcc: string[]
	}
	reply_to: { display_name: string; email: string }[]
	attachments: Attachment[]
	user_image?: string
	collapsed?: boolean
}

export interface ComposeMailData {
	name?: string
	id?: string
	from_email?: string
	to?: string[]
	cc?: string[]
	bcc?: string[]
	subject?: string
	quoted_content?: string
	html_body?: string
	attachments?: Attachment[]
	in_reply_to?: string
	in_reply_to_id?: string
	forwarded_from_id?: string
	type?: 'reply' | 'replyAll' | 'forward'
}

export interface Thread {
	name: string
	account: string
	thread_id: string
	from_name: string
	from_email: string
	subject: string | null
	preview: string | null
	has_attachment: 0 | 1
	received_at: string
	mailboxes: Mailbox[]
	recipients: Recipient[]
	seen: 0 | 1
	draft: 0 | 1
	junk: 0 | 1
	flagged: 0 | 1
	answered: 0 | 1
	forwarded: 0 | 1
	attachments: Attachment[]
	user_image?: string
}

export interface MailboxData {
	id: string
	role: string | null
	total_threads: number
	unread_threads: number
	_name: string
}

export interface NotificationPayload {
	data?: {
		title?: string
		body?: string
		notification_icon?: string
		click_action?: string
	}
}
