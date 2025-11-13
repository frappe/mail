/* eslint-disable @typescript-eslint/no-explicit-any */

interface DocType {
	name: string
	creation: string
	modified: string
	owner: string
	modified_by: string
	docstatus: 0 | 1 | 2
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

// Last updated: 2025-07-17 13:00:14.427328
export interface MailAccountRequest extends DocType {
	/** Request Key: Data */
	request_key?: string
	/** Email: Data */
	email: string
	/** Tenant: Link (Mail Tenant) */
	tenant?: string
	/** OTP: Data */
	otp?: string
	/** Invited By: Link (User) */
	invited_by?: string
	/** Is Verified: Check */
	is_verified: 0 | 1
	/** Is Expired: Check */
	is_expired: 0 | 1
	/** Is Invite: Check */
	is_invite: 0 | 1
	/** Account: Data */
	account?: string
	/** Domain: Link (Mail Domain) */
	domain_name?: string
	/** Is Admin: Check */
	is_admin: 0 | 1
	/** Send Invite: Check */
	send_invite: 0 | 1
	/** IP Address: Data */
	ip_address?: string
	/** Expires At: Datetime */
	expires_at?: string
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
	/** Tenant: Link (Mail Tenant) */
	tenant: string
	/** Default Disk Quota (in GB): Float */
	default_disk_quota?: number
}

// Last updated: 2025-07-17 13:00:45.874699
export interface MailAlias extends DocType {
	/** Enabled: Check */
	enabled: 0 | 1
	/** Domain Name: Link (Mail Domain) */
	domain_name: string
	/** Email: Data */
	email: string
	/** Alias For (Type): Select */
	alias_for_type: '' | 'Mail Account' | 'Mailing List'
	/** Alias For (Name): Dynamic Link (alias_for_type) */
	alias_for_name: string
	/** Tenant: Link (Mail Tenant) */
	tenant?: string
	/** Normalized Email: Data */
	normalized_email?: string
}

// Last updated: 2025-08-21 18:54:47.654063
export interface MailTenant extends DocType {
	/** Tenant Name: Data */
	tenant_name: string
	/** Logo: Attach Image */
	logo?: string
	/** Maximum No. of Domains: Int */
	max_domains: number
	/** Maximum No. of Accounts: Int */
	max_accounts: number
	/** User: Link (User) */
	user: string
	/** Allow Personal Signup: Check */
	allow_personal_signup: 0 | 1
	/** Cluster: Link (Mail Cluster) */
	cluster?: string
	/** Maximum No. of Mailing Lists: Int */
	max_mailing_lists: number
}

// Last updated: 2025-01-31 15:53:10.550269
export interface MailTenantMember extends DocType {
	/** User: Link (User) */
	user: string
	/** Tenant: Link (Mail Tenant) */
	tenant: string
	/** Is Admin: Check */
	is_admin: 0 | 1
}

// Last updated: 2025-01-28 15:33:09.730936
export interface MailDomainRequest extends DocType {
	/** Domain Name: Data */
	domain_name: string
	/** User: Link (User) */
	user: string
	/** Verification Key: Data */
	verification_key?: string
	/** Is Verified: Check */
	is_verified: 0 | 1
	/** Tenant: Link (Mail Tenant) */
	tenant: string
}

// Last updated: 2025-09-15 18:39:21.316684
export interface MailAccount extends DocType {
	/** Enabled: Check */
	enabled: 0 | 1
	/** Create Mail Contact: Check */
	create_mail_contact: 0 | 1
	/** Domain Name: Link (Mail Domain) */
	domain_name: string
	/** User: Link (User) */
	user: string
	/** Email: Data */
	email?: string
	/** Display Name: Data */
	display_name?: string
	/** Reply To: Small Text */
	reply_to?: string
	/** Default Email: Data */
	default_outgoing_email?: string
	/** Tenant: Link (Mail Tenant) */
	tenant?: string
	/** Normalized Email: Data */
	normalized_email?: string
	/** Backup Email: Data */
	backup_email: string
	/** Override Display Name: Check */
	override_display_name: 0 | 1
	/** Override Reply To: Check */
	override_reply_to: 0 | 1
	/** Enabled: Check */
	vacation_response_enabled: 0 | 1
	/** From Date: Datetime */
	vacation_from_date?: string
	/** To Date: Datetime */
	vacation_to_date?: string
	/** Subject: Small Text */
	vacation_response_subject?: string
	/** Text: Code */
	vacation_response_text_body?: string
	/** HTML: Text Editor */
	vacation_response_html_body?: string
	/** Destroy Email After Submission: Check */
	destroy_email_after_submission: 0 | 1
	/** Destroy Newsletter After Submission: Check */
	destroy_newsletter_after_submission: 0 | 1
	/** Disk Quota (in GB): Float */
	disk_quota?: number
	/** Used Quota (in GB): Float */
	used_quota?: number
	/** Quota Usage: Percent */
	quota_usage?: number
	/** Disk Quota: Int */
	_disk_quota?: number
	/** Used Quota: Int */
	_used_quota?: number
	/** App Password: Password */
	app_password?: string
	/** Secret Hash: Small Text */
	secret_hash?: string
}

// Last updated: 2025-03-26 11:43:10.481605
export interface PersonalSignupDomain extends ChildDocType {
	/** Domain Name: Link (Mail Domain) */
	domain_name: string
}

// Last updated: 2025-10-13 12:32:43.976269
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
	/** TTL: Int */
	default_ttl: number
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
	/** DKIM RSA Key Size: Select */
	default_dkim_rsa_key_size: '' | '2048' | '4096'
	/** Allow Business Signup: Check */
	allow_business_signup: 0 | 1
	/** Allow Personal Signup: Check */
	allow_personal_signup: 0 | 1
	/** Personal Signup Domains: Table MultiSelect (Personal Signup Domain) */
	personal_signup_domains: PersonalSignupDomain[]
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

// Last updated: 2025-07-17 13:01:50.810837
export interface MailContact extends DocType {
	/** User: Link (User) */
	user: string
	/** Email: Data */
	email: string
	/** Display Name: Data */
	display_name?: string
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

// Last updated: 2025-08-14 19:12:08.055725
export interface MailMessageReplyTo extends ChildDocType {
	/** Display Name: Data */
	display_name?: string
	/** Email: Data */
	email: string
}

// Last updated: 2025-09-30 19:33:57.028536
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
}

// Last updated: 2025-11-11 14:57:57.517275
export interface MailMessage extends DocType {
	/** Account: Link (Mail Account) */
	account: string
	/** From Name: Data */
	from_name?: string
	/** From Email: Data */
	from_email?: string
	/** Subject: Small Text */
	subject?: string
	/** undefined: Table (Mail Message Reply To) */
	reply_to: MailMessageReplyTo[]
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
	/** Mail ID: Data */
	_id?: string
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

// Last updated: 2025-07-17 13:00:30.774415
export interface MailingList extends DocType {
	/** Enabled: Check */
	enabled: 0 | 1
	/** Domain Name: Link (Mail Domain) */
	domain_name: string
	/** Email: Data */
	email: string
	/** Display Name: Data */
	display_name?: string
	/** Tenant: Link (Mail Tenant) */
	tenant?: string
	/** Normalized Email: Data */
	normalized_email?: string
}

// Last updated: 2025-06-02 13:39:11.904000
export interface MailingListMember extends DocType {
	/** Member (Type): Select */
	member_type: 'Mail Account'
	/** Member (Name): Dynamic Link (member_type) */
	member_name: string
	/** Mailing List: Link (Mailing List) */
	mailing_list: string
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
