interface DocType {
	name: string
	creation: string
	modified: string
	owner: string
	modified_by: string
}

interface ChildDocType extends DocType {
	parent?: string
	parentfield?: string
	parenttype?: string
	idx?: number
}

// Last updated: 2025-02-19 19:18:44.222087
export interface MailRecipient extends ChildDocType {
	/** Display Name: Data */
	display_name?: string
	/** Status: Select */
	status?: '' | 'Blocked' | 'Sent'
	/** Type: Select */
	type: 'To' | 'Cc' | 'Bcc'
	/** Email: Data */
	email: string
	/** Error Message: Code */
	error_message?: string
}

// Last updated: 2025-02-03 17:11:14.640642
export interface MailHeader extends ChildDocType {
	/** Key: Data */
	key: string
	/** Value: Text */
	value?: string
}

// Last updated: 2026-04-13 10:27:23.941932
export interface MailAccountRequest extends DocType {
	/** Request Key: Data */
	request_key?: string
	/** Backup Email: Data */
	backup_email: string
	/** Invited By: Link (User) */
	invited_by: string
	/** Is Verified: Check */
	is_verified: 0 | 1
	/** Is Expired: Check */
	is_expired: 0 | 1
	/** Account: Data */
	account: string
	/** Domain: Data */
	domain_name: string
	/** Send Invite: Check */
	send_invite: 0 | 1
	/** IP Address: Data */
	ip_address?: string
	/** Expires At: Datetime */
	expires_at?: string
	/** Roles: Small Text */
	roles: string
}

// Last updated: 2025-02-03 17:11:17.517836
export interface MailDomainDNSRecord extends ChildDocType {
	/** Type: Select */
	type: '' | 'A' | 'AAAA' | 'CNAME' | 'MX' | 'TXT'
	/** Host: Data */
	host: string
	/** Value: Text */
	value: string
	/** Priority: Int */
	priority?: number
	/** TTL (Recommended): Int */
	ttl: number
	/** Category: Select */
	category: '' | 'Sending Record' | 'Receiving Record' | 'Tracking Record' | 'Server Record'
}

// Last updated: 2025-07-15 16:20:27.181885
export interface MailDomain extends DocType {
	/** Domain Name: Data */
	domain_name: string
	/** DNS Records: Table (Mail Domain DNS Record) */
	dns_records: MailDomainDNSRecord[]
	/** Enabled: Check */
	enabled: 0 | 1
	/** Verified: Check */
	is_verified: 0 | 1
	/** Subdomain: Check */
	is_subdomain: 0 | 1
	/** DKIM RSA Key Size: Select */
	dkim_rsa_key_size?: '' | '2048' | '4096'
	/** Root Domain: Check */
	is_root_domain: 0 | 1
	/** Default Disk Quota (in GB): Float */
	default_disk_quota?: number
}

// Last updated: 2026-04-12 23:51:49.709930
export interface MailDomainRequest extends DocType {
	/** Domain Name: Data */
	domain_name: string
	/** User: Link (User) */
	user: string
	/** Verification Key: Data */
	verification_key?: string
	/** Is Verified: Check */
	is_verified: 0 | 1
}

// Last updated: 2025-11-27 13:25:44.326974
export interface SignupDomain extends ChildDocType {
	/** Domain: Link (Principal Settings) */
	principal: string
}

// Last updated: 2026-04-08 09:54:08.953300
export interface MailSettings extends DocType {
	/** Root Domain Name: Data */
	root_domain_name: string
	/** DNS Provider: Select */
	dns_provider?:
		| ''
		| 'AmazonRoute53'
		| 'DigitalOcean'
		| 'Cloudflare'
		| 'Hetzner'
		| 'Linode'
		| 'Namecheap'
		| 'GoDaddy'
	/** Token: Password */
	dns_provider_token?: string
	/** JMAP Push Key (P256DH): Data */
	jmap_push_p256dh?: string
	/** JMAP Push Private Key: Password */
	jmap_push_private_key?: string
	/** JMAP Push Auth Secret: Password */
	jmap_push_auth?: string
	/** Host: Data */
	spamd_host?: string
	/** Port: Int */
	spamd_port?: number
	/** Scanning Mode: Select */
	spamd_scanning_mode?: 'Exclude Attachments' | 'Include Attachments' | 'Hybrid Approach'
	/** Hybrid Scanning Threshold: Float */
	spamd_hybrid_scanning_threshold?: number
	/** Enable Spam Detection: Check */
	enable_spamd: 0 | 1
	/** Allow Signup: Check */
	allow_signup: 0 | 1
	/** Signup Domains: Table MultiSelect (Personal Signup Domain) */
	signup_domains: SignupDomain[]
	/** Username: Data */
	dns_provider_username?: string
	/** Zone ID: Data */
	dns_provider_zone_id?: string
	/** Key: Data */
	dns_provider_key?: string
	/** Secret: Password */
	dns_provider_secret?: string
	/** Client IP: Data */
	dns_provider_client_ip?: string
	/** Private Zone: Check */
	dns_provider_private_zone: 0 | 1
	/** Access Key: Data */
	dns_provider_access_key?: string
	/** Access Secret: Password */
	dns_provider_access_secret?: string
}

// Last updated: 2025-08-14 19:12:30.003138
export interface MailMessageRecipient extends ChildDocType {
	/** Type: Select */
	type: 'To' | 'Cc' | 'Bcc'
	/** Display Name: Data */
	display_name?: string
	/** Email: Data */
	email: string
}

// Last updated: 2025-11-20 15:22:07.630230
export interface EmailAddress extends ChildDocType {
	/** Display Name: Data */
	display_name?: string
	/** Email: Data */
	email: string
}

// Last updated: 2026-03-12 20:02:37.173596
export interface MailMessagePart extends ChildDocType {
	/** Part ID: Data */
	part_id?: string
	/** File Name: Data */
	filename?: string
	/** Charset: Data */
	charset?: string
	/** Disposition: Select */
	disposition?: '' | 'inline' | 'attachment'
	/** Language: Data */
	language?: string
	/** Location: Data */
	location?: string
	/** File URL: Attach */
	file_url?: any
	/** Type: Data */
	type?: string
	/** Blob ID: Data */
	blob_id?: string
	/** Size: Int */
	size?: number
	/** Content ID: Data */
	cid?: string
	/** URL: Data */
	url?: string
	/** undefined: Image */
	image?: any
}

// Last updated: 2026-04-17 14:04:45.131751
export interface MailMessage extends DocType {
	/** From Name: Data */
	from_name?: string
	/** From Email: Data */
	from_email?: string
	/** Subject: Small Text */
	subject?: string
	/** undefined: Table (Email Address) */
	reply_to: EmailAddress[]
	/** undefined: Table (Mail Message Recipient) */
	recipients: MailMessageRecipient[]
	/** HTML: Code */
	html_body?: string
	/** Text: Code */
	text_body?: string
	/** Attachments: Table (Mail Message Part) */
	attachments: MailMessagePart[]
	/** Message ID: Data */
	message_id?: string
	/** Blob ID: Data */
	blob_id?: string
	/** Size: Int */
	size?: number
	/** Has Attachment: Check */
	has_attachment: 0 | 1
	/** Sent At: Datetime */
	sent_at?: string
	/** Received At: Datetime */
	received_at?: string
	/** Received After (Seconds): Float */
	received_after?: number
	/** Sender Name: Data */
	sender_name?: string
	/** Sender Email: Data */
	sender_email?: string
	/** In Reply To (Message ID): Data */
	in_reply_to?: string
	/** Thread ID: Data */
	thread_id?: string
	/** Draft: Check */
	draft: 0 | 1
	/** Seen: Check */
	seen: 0 | 1
	/** Flagged: Check */
	flagged: 0 | 1
	/** Answered: Check */
	answered: 0 | 1
	/** Forwarded: Check */
	forwarded: 0 | 1
	/** Keywords: JSON */
	keywords?: any
	/** From IP: Data */
	from_ip?: string
	/** From Host: Data */
	from_host?: string
	/** Spam Score: Float */
	spam_score?: number
	/** SPF: Check */
	spf_pass: 0 | 1
	/** DKIM: Check */
	dkim_pass: 0 | 1
	/** DMARC: Check */
	dmarc_pass: 0 | 1
	/** SPF Description: Small Text */
	spf_description?: string
	/** DKIM Description: Small Text */
	dkim_description?: string
	/** DMARC Description: Small Text */
	dmarc_description?: string
	/** HTML Body: Table (Mail Message Part) */
	_html_body: MailMessagePart[]
	/** Text Body: Table (Mail Message Part) */
	_text_body: MailMessagePart[]
	/** Message: Code */
	message?: string
	/** undefined: Table (Mail Message Mailbox) */
	mailboxes: MailMessageMailbox[]
	/** Preview: Code */
	preview?: string
	/** Junk: Check */
	junk: 0 | 1
	/** Mail ID: Data */
	id?: string
	/** Before: Datetime */
	before?: string
	/** After: Datetime */
	after?: string
	/** Min Size (Bytes): Int */
	min_size?: number
	/** Max Size (Bytes): Int */
	max_size?: number
	/** In Mailbox: Data */
	in_mailbox?: string
	/** Has Keyword: Data */
	has_keyword?: string
	/** Not Keyword: Data */
	not_keyword?: string
	/** Text: Data */
	text?: string
	/** From: Data */
	_from?: string
	/** To: Data */
	_to?: string
	/** Cc: Data */
	_cc?: string
	/** Bcc: Data */
	_bcc?: string
	/** Body: Data */
	body?: string
	/** Account: Select */
	account: any
	/** User: Link (User) */
	user?: string
}

// Last updated: 2025-01-15 11:46:42.917146
export interface File extends DocType {
	/** File Name: Data */
	file_name?: string
	/** Is Private: Check */
	is_private: 0 | 1
	/** Is Home Folder: Check */
	is_home_folder: 0 | 1
	/** Is Attachments Folder: Check */
	is_attachments_folder: 0 | 1
	/** File Size: Int */
	file_size?: number
	/** File URL: Code */
	file_url?: string
	/** Thumbnail URL: Small Text */
	thumbnail_url?: string
	/** Folder: Link (File) */
	folder?: string
	/** Is Folder: Check */
	is_folder: 0 | 1
	/** Attached To DocType: Link (DocType) */
	attached_to_doctype?: string
	/** Attached To Name: Data */
	attached_to_name?: string
	/** Attached To Field: Data */
	attached_to_field?: string
	/** old_parent: Data */
	old_parent?: string
	/** Content Hash: Data */
	content_hash?: string
	/** Uploaded To Dropbox: Check */
	uploaded_to_dropbox: 0 | 1
	/** Uploaded To Google Drive: Check */
	uploaded_to_google_drive: 0 | 1
	/** File Type: Data */
	file_type?: string
}

// Last updated: 2025-08-14 22:57:14.397697
export interface MailMessageMailbox extends ChildDocType {
	/** Mailbox: Link (Mailbox) */
	mailbox: string
	/** Mailbox ID: Data */
	mailbox_id: string
	/** Mailbox Name: Data */
	mailbox_name: string
}

// Last updated: 2026-04-17 13:35:58.399195
export interface Identity extends DocType {
	/** May Delete: Check */
	may_delete: 0 | 1
	/** Identity ID: Data */
	id?: string
	/** Name: Data */
	_name?: string
	/** Email: Data */
	email: string
	/** Bcc: Table (Email Address) */
	bcc: EmailAddress[]
	/** Reply To: Table (Email Address) */
	reply_to: EmailAddress[]
	/** HTML: HTML Editor */
	html_signature?: any
	/** Text: Code */
	text_signature?: string
	/** Account: Select */
	account: any
	/** User: Link (User) */
	user?: string
}

// Last updated: 2026-04-16 12:20:38.930196
export interface MailSignature extends DocType {
	/** Signature Name: Data */
	signature_name: string
	/** HTML: Code */
	html_body?: string
	/** User: Link (User) */
	user: string
}

// Last updated: 2026-04-17 14:12:49.529770
export interface VacationResponse extends DocType {
	/** Enabled: Check */
	enabled: 0 | 1
	/** From Date: Datetime */
	from_date?: string
	/** To Date: Datetime */
	to_date?: string
	/** Subject: Data */
	subject?: string
	/** Text: Code */
	text_body?: string
	/** HTML: Text Editor */
	html_body?: string
	/** Account: Select */
	account: any
	/** User: Link (User) */
	user?: string
}

// Last updated: 2026-04-15 08:27:17.244854
export interface UserAccount extends DocType {
	/** User: Link (User) */
	user: string
	/** Name: Data */
	_name: string
	/** Personal: Check */
	is_personal: 0 | 1
	/** Readonly: Check */
	is_read_only: 0 | 1
	/** Account ID: Data */
	id: string
	/** Capabilities: JSON */
	capabilities?: any
}
