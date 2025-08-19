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
	email_addresses: string[]
	default_outgoing: string

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

export interface Attachment {
	filename: string
	blob_id: string
	type: string
	size: string
	file_url: string | null
	disposition: string
}

export interface Mail {
	name: string
	message_id: string
	_id: string
	from_name: string
	from_email: string
	subject: string
	html_body: string
	text_body: string
	received_at: string
	mailbox_id: string
	draft: 0 | 1
	flagged: 0 | 1
	seen: 0 | 1
	recipients: Recipient[]
	reply_to: string[]
	attachments: Attachment[]
	collapsed?: boolean
}

export interface ComposeMailData {
	from_email: string
	to: string[]
	cc: string[]
	bcc: string[]
	subject: string
	html_body: string
	attachments: Attachment[]
	in_reply_to: string
	in_reply_to_id: string
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
	mailbox_id: string
	seen: 0 | 1
	draft: 0 | 1
	flagged: 0 | 1
	answered: 0 | 1
	forwarded: 0 | 1
	attachments: Attachment[]
}

export type LayoutType = 'split' | 'full'
