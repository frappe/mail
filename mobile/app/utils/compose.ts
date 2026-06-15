// Builds the ComposeMailData pre-fill for reply / reply-all / forward, ported from
// the web frontend/src/components/MailThread.vue so mobile matches its behaviour.

import dayjs from 'dayjs'

import { groupRecipients } from '@/utils/format'

import type { ComposeMailData, DraftRecipient, Mail, Recipient } from '@mail/types'

// Recipients of one type as compose chips (email + display name).
function pick(recipients: Recipient[], type: Recipient['type']): DraftRecipient[] {
	return (recipients || [])
		.filter((r) => r.type === type)
		.map((r) => ({ email: r.email, display_name: r.display_name ?? undefined }))
}

const isUserEmail = (email: string, userEmails: string[]) => userEmails.includes(email)

// Mirrors the web hasHtmlContent (regex-only, no DOM — safe in NativeScript).
function hasHtmlContent(content?: string): boolean {
	if (!content) return false
	return /<(html|head|body|div|p|span|table|td|tr|a|img|br|hr|h[1-6]|ul|ol|li|strong|em|b|i|font|style)[^>]*>/i.test(
		content,
	)
}

function bodyContent(mail: Mail): string {
	if (hasHtmlContent(mail.html_body)) return mail.html_body
	return `<pre style="white-space: pre-wrap; word-break: break-word">${mail.html_body || mail.text_body || '&nbsp;'}</pre>`
}

function quotedContent(mail: Mail): string {
	return `
		<div class="frappe_mail_quote">
			On ${dayjs(mail.received_at).format('DD MMM YYYY [at] h:mm A')}, ${mail.from_email} wrote:
			<blockquote style="margin-left: 8px">
				${bodyContent(mail)}
			</blockquote>
		</div>
	`
}

function forwardedContent(mail: Mail): string {
	const r = groupRecipients(mail.recipients)
	return `
		<div class="frappe_mail_fwd">
			<br><br>
			---------- Forwarded message ---------<br>
			From: ${mail.from_name} < ${mail.from_email} ><br>
			Date: ${dayjs(mail.received_at).format('ddd, MMM D, YYYY [at] h:mm A')}<br>
			Subject: ${mail.subject || ''}<br>
			To: ${r.to}<br>
			${r.cc ? `Cc: ${r.cc}<br>` : ''}
			<br><br>
			${bodyContent(mail)}
		</div>
	`
}

function replyDetails(mail: Mail): ComposeMailData {
	return {
		subject: mail.subject?.startsWith('Re: ') ? mail.subject : `Re: ${mail.subject ?? ''}`,
		quoted_content: quotedContent(mail),
		in_reply_to: mail.message_id,
		in_reply_to_id: mail.id,
	}
}

// Reply goes to the original sender (or the recipients, if you sent it), falling
// back to Reply-To when present.
function replyRecipients(mail: Mail, userEmails: string[]): { to: DraftRecipient[] } {
	if (isUserEmail(mail.from_email, userEmails)) return { to: pick(mail.recipients, 'To') }
	if (mail.reply_to?.length)
		return { to: mail.reply_to.map((r) => ({ email: r.email, display_name: r.display_name })) }
	return { to: [{ email: mail.from_email, display_name: mail.from_name }] }
}

function replyAllRecipients(
	mail: Mail,
	userEmails: string[],
): { to: DraftRecipient[]; cc: DraftRecipient[] } {
	if (isUserEmail(mail.from_email, userEmails))
		return { to: pick(mail.recipients, 'To'), cc: pick(mail.recipients, 'Cc') }

	const to = mail.reply_to?.length
		? mail.reply_to.map((r) => ({ email: r.email, display_name: r.display_name }))
		: [{ email: mail.from_email, display_name: mail.from_name }]
	const cc = [...pick(mail.recipients, 'To'), ...pick(mail.recipients, 'Cc')].filter(
		(r) => !isUserEmail(r.email, userEmails),
	)
	return { to, cc }
}

export function buildReply(mail: Mail, userEmails: string[]): ComposeMailData {
	return { ...replyDetails(mail), ...replyRecipients(mail, userEmails), type: 'reply' }
}

export function buildReplyAll(mail: Mail, userEmails: string[]): ComposeMailData {
	return { ...replyDetails(mail), ...replyAllRecipients(mail, userEmails), type: 'replyAll' }
}

// Open an existing draft for editing: prefill from the saved message and carry its
// `id` so ComposeView updates the draft (update_draft_mail) instead of creating one.
// The whole html_body goes into the body (the saved draft already merged any quote).
export function buildDraftEdit(mail: Mail): ComposeMailData {
	return {
		id: mail.id,
		from_email: mail.from_email,
		to: pick(mail.recipients, 'To'),
		cc: pick(mail.recipients, 'Cc'),
		bcc: pick(mail.recipients, 'Bcc'),
		subject: mail.subject ?? '',
		html_body: mail.html_body ?? '',
	}
}

export function buildForward(mail: Mail): ComposeMailData {
	return {
		subject: mail.subject?.startsWith('Fwd: ') ? mail.subject : `Fwd: ${mail.subject ?? ''}`,
		// Carried as quoted_content (not html_body) so it starts collapsed behind the
		// in-body ··· toggle, like a reply quote.
		quoted_content: forwardedContent(mail),
		forwarded_from_id: mail.id,
		type: 'forward',
	}
}
