// Pure formatting utilities — no DOM/browser dependencies, safe to use in NativeScript.
// Mirrors helpers from frontend/src/utils/index.ts and frontend/src/utils/dayjs.ts.

import dayjs from 'dayjs'
import isToday from 'dayjs/plugin/isToday'
import isYesterday from 'dayjs/plugin/isYesterday'
import localizedFormat from 'dayjs/plugin/localizedFormat'
import relativeTime from 'dayjs/plugin/relativeTime'

import type { Recipient } from '@mail/types'

dayjs.extend(relativeTime)
dayjs.extend(localizedFormat)
dayjs.extend(isToday)
dayjs.extend(isYesterday)

export function toTitleCase(str: string): string {
	return (
		str
			?.toLowerCase()
			.split(' ')
			.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
			.join(' ') || ''
	)
}

export function formatBytes(bytes: number): string {
	if (!+bytes) return '0 B'
	const k = 1024
	const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
	const i = Math.floor(Math.log(bytes) / Math.log(k))
	return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

export function formatDate(date: string | Date): string {
	const d = dayjs(date)
	if (d.isToday()) return d.format('h:mm A')
	if (d.year() === dayjs().year()) return d.format('MMM D')
	return d.format('MMM D, YYYY')
}

// Relative "x hours ago" for the thread detail message header, capitalized to
// match the web MailDate.vue (which uses useTimeAgo in the non-list view).
export function formatTimeAgo(date: string | Date): string {
	const s = dayjs(date).fromNow()
	return s.charAt(0).toUpperCase() + s.slice(1)
}

export function formatRelative(date: string | Date): string {
	return dayjs(date).fromNow()
}

// Compact timestamp for thread list rows (mirrors the Mail Mobile design):
// today → time, yesterday → "Yesterday", this year → "MMM D", else "MMM D, YYYY".
export function formatListDate(date: string | Date): string {
	const d = dayjs(date)
	if (d.isToday()) return d.format('h:mm A')
	if (d.isYesterday()) return __('Yesterday')
	if (d.year() === dayjs().year()) return d.format('MMM D')
	return d.format('MMM D, YYYY')
}

// "To: <names>" header used for outgoing threads (sent/drafts), mirroring the
// web getFormattedRecipients. Falls back to all recipients when none are "To".
export function formatRecipients(recipients: Recipient[]): string {
	if (!recipients?.length) return __('To:')
	const to = recipients.filter((r) => r.type === 'To')
	const list = (to.length ? to : recipients).map((r) => r.display_name || r.email)
	return `${__('To:')} ${list.join(', ')}`
}
