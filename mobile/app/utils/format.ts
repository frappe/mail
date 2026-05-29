// Pure formatting utilities — no DOM/browser dependencies, safe to use in NativeScript.
// Mirrors helpers from frontend/src/utils/index.ts and frontend/src/utils/dayjs.ts.

import dayjs from 'dayjs'
import isToday from 'dayjs/plugin/isToday'
import localizedFormat from 'dayjs/plugin/localizedFormat'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)
dayjs.extend(localizedFormat)
dayjs.extend(isToday)

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

export function formatRelative(date: string | Date): string {
	return dayjs(date).fromNow()
}
