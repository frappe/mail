import * as cheerio from 'cheerio'
import { File, Paperclip } from 'lucide-vue-next'
import { toast } from 'frappe-ui'

import dayjs from '@/utils/dayjs'
import AudioIcon from '@/components/Icons/AudioIcon.vue'
import ImageIcon from '@/components/Icons/ImageIcon.vue'
import PDFIcon from '@/components/Icons/PDFIcon.vue'
import VideoIcon from '@/components/Icons/VideoIcon.vue'

import type { ComposeMailData, Recipient } from '@/types'

export const toTitleCase = (str: string) =>
	str
		?.toLowerCase()
		.split(' ')
		.map(function (word: string) {
			return word.charAt(0).toUpperCase().concat(word.substr(1))
		})
		.join(' ') || ''

export function startResizing(event) {
	const startX = event.clientX
	const sidebar = document.getElementsByClassName('mailSidebar')[0]
	const startWidth = sidebar.offsetWidth

	const onMouseMove = (event) => {
		const diff = event.clientX - startX
		let newWidth = startWidth + diff
		if (newWidth < 200) {
			newWidth = 200
		}
		sidebar.style.width = newWidth + 'px'
	}

	const onMouseUp = () => {
		document.removeEventListener('mousemove', onMouseMove)
		document.removeEventListener('mouseup', onMouseUp)
	}

	document.addEventListener('mousemove', onMouseMove)
	document.addEventListener('mouseup', onMouseUp)
}

export const singularize = (word: string) => {
	const endings = {
		ves: 'fe',
		ies: 'y',
		i: 'us',
		zes: 'ze',
		ses: 's',
		es: 'e',
		s: '',
	}
	return word.replace(new RegExp(`(${Object.keys(endings).join('|')})$`), (r) => endings[r])
}

export const validateEmail = (email: string) => {
	const regExp =
		/^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/
	return regExp.test(email)
}

export const formatBytes = (bytes: number) => {
	if (!+bytes) return '0 Bytes'

	const k = 1024
	const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']

	const i = Math.floor(Math.log(bytes) / Math.log(k))

	return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

export const raiseToast = (message: string, type = 'success') => {
	if (type === 'success') return toast.success(message)

	const div = document.createElement('div')
	div.innerHTML = message
	// strip html tags
	const text =
		div.textContent || div.innerText || __('Failed to perform action. Please try again later.')
	toast.error(text)
}

export const raisePromiseToast = (
	action: () => Promise<unknown>,
	loading: string,
	success: string,
	undoAction?: () => void,
) => {
	toast.removeAll()

	const error = __('Action failed. Please try again later.')

	if (undoAction)
		return toast.promise(action(), {
			loading,
			success,
			error,
			successAction: { label: __('Undo'), onClick: () => undoAction() },
		})

	toast.promise(action(), { loading, success, error })
}

export const kebabToTitleCase = (str: string) =>
	str
		.split('-')
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(' ')

export const copyToClipBoard = async (text: string) => {
	try {
		await navigator.clipboard.writeText(text)
		raiseToast(__('Copied to clipboard.'))
	} catch {
		raiseToast(__('Failed to copy.'), 'error')
	}
}

export const getGroupedRecipients = (
	recipients: Recipient[],
	formatToString = true,
	showEmail = false,
) => {
	const to = []
	const cc = []
	const bcc = []

	for (const r of recipients) {
		if (r.type === 'To') to.push(formatToString ? r : r.email)
		else if (r.type === 'Cc') cc.push(formatToString ? r : r.email)
		else if (r.type === 'Bcc') bcc.push(formatToString ? r : r.email)
	}

	if (!formatToString) return { to, cc, bcc }

	const format = (list: Recipient[]) =>
		list
			?.map(({ display_name, email }) =>
				showEmail && display_name ? `${display_name} <${email}>` : display_name || email,
			)
			.join(', ')

	return {
		to: format(to as Recipient[]),
		cc: format(cc as Recipient[]),
		bcc: format(bcc as Recipient[]),
	}
}

export const getFormattedRecipients = (mailRecipients: Recipient[]) => {
	const groupedRecipients = getGroupedRecipients(mailRecipients)

	let formattedRecipients = ''
	if (groupedRecipients.to) formattedRecipients += __('To:') + ` ${groupedRecipients.to} `
	if (groupedRecipients.cc) formattedRecipients += __('Cc:') + ` ${groupedRecipients.cc} `
	if (groupedRecipients.bcc) formattedRecipients += __('Bcc:') + ` ${groupedRecipients.bcc} `
	return formattedRecipients
}

export const getFormattedDate = (date: Date | string, omitDate = false) => {
	const dateObj = dayjs(date)
	const isCurrentYear = dateObj.year() === dayjs().year()
	if (omitDate) return dateObj.format(isCurrentYear ? 'MMMM' : 'MMMM YYYY')
	if (dateObj.isToday()) return __('Today')
	if (dateObj.isYesterday()) return __('Yesterday')
	return dateObj.format(isCurrentYear ? 'D MMMM' : 'D MMMM YYYY')
}

export const getFirstAlphabet = (str?: string) => str?.match(/\p{L}/u)?.[0]

export const getTheme = (
	status: 'Draft' | 'Queued' | 'In Progress' | 'Completed' | 'Failed' | 'Cancelled',
) => {
	switch (status) {
		case 'Draft':
			return 'gray'
		case 'Completed':
			return 'green'
		case 'Failed':
		case 'Cancelled':
			return 'red'
		default:
			return 'blue'
	}
}

export const extractQuotedContent = (htmlBody?: string) => {
	if (!htmlBody) return { quoted_content: '', html_body: '' }

	const parser = new DOMParser()
	const doc = parser.parseFromString(htmlBody, 'text/html')

	const topLevelDiv = Array.from(doc.body.children).find(
		(el) => el.tagName.toLowerCase() === 'div' && el.classList.contains('frappe_mail_quote'),
	)

	let quoted_content = ''
	if (topLevelDiv) {
		quoted_content = topLevelDiv.outerHTML
		topLevelDiv.remove()
	}

	return { quoted_content, html_body: doc.body.innerHTML }
}

export const isMac = navigator.platform.toUpperCase().includes('MAC')

export const isOverlayPresent = () =>
	!!document.querySelector(
		'[role="dialog"]:not([role="alert"]), [role="alertdialog"], .modal-open, [data-state="open"]:not([data-reka-collection-item]), [data-attachment-viewer]',
	)

export const shouldIgnoreKeypress = (
	e: KeyboardEvent,
	allowCtrlAndMeta: boolean = false,
): boolean => {
	if (isOverlayPresent()) return true

	if (!allowCtrlAndMeta && (e.ctrlKey || e.metaKey)) return true

	const target = e.target as HTMLElement
	return (
		(target.tagName === 'INPUT' && (target as HTMLInputElement).type !== 'checkbox') ||
		target.tagName === 'TEXTAREA' ||
		target.isContentEditable ||
		e.altKey
	)
}

export const convertHtmlToText = (html: string) => {
	if (!html) return ''

	const parser = new DOMParser()
	const doc = parser.parseFromString(html, 'text/html')
	const body = doc.body || doc.documentElement

	const anchors = body.querySelectorAll('a')
	const buttons = body.querySelectorAll('button')
	const inputs = body.querySelectorAll('input')

	anchors.forEach((anchor) => {
		const text = document.createTextNode(anchor.textContent)
		anchor.parentNode?.replaceChild(text, anchor)
	})

	buttons.forEach((button) => button.remove())

	inputs.forEach((input) => {
		const type = input.getAttribute('type') || 'text'
		if (['button', 'submit', 'reset'].includes(type)) {
			input.remove()
		}
	})

	const text = body.textContent || body.innerText || ''
	return text.replace(/\s+/g, ' ').trim()
}

export const isEmail = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)

export const getFileIcon = (type?: string) => {
	if (!type) return Paperclip
	if (type?.startsWith('image/')) return ImageIcon
	if (type === 'application/pdf') return PDFIcon
	if (type?.startsWith('video/')) return VideoIcon
	if (type?.startsWith('audio/')) return AudioIcon

	return File
}

export const randomString = (length: number) => {
	const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
	let result = ''
	for (let i = 0; i < length; i++) {
		result += chars.charAt(Math.floor(Math.random() * chars.length))
	}
	return result
}

export const processInlineImages = (mail: ComposeMailData) => {
	const htmlBody = mail.html_body! + mail.quoted_content
	const $ = cheerio.load(htmlBody)

	const regularAttachments = mail.attachments?.filter((a) => a.disposition !== 'inline') || []
	const inlineAttachments = mail.attachments?.filter((a) => a.disposition === 'inline') || []
	const processedAttachments = [...regularAttachments]

	$('img').each((_, img) => {
		const $img = $(img)
		const src = $img.attr('src')
		if (!src) return

		const cid = $img.attr('data-cid')
		if (!cid) return

		$img.attr('src', `cid:${cid}`)

		if (src.startsWith('/files') || src.startsWith('/private/files')) {
			processedAttachments.push({ file_url: src, disposition: 'inline', cid })
			return
		}

		const url = new URL(src)
		const blob_id = url.searchParams.get('blob_id')
		if (!blob_id) return

		const attachment = inlineAttachments.find((a) => a.blob_id === blob_id)
		if (attachment) processedAttachments.push({ ...attachment, cid })
	})

	return { html_body: $.html(), attachments: processedAttachments }
}

export const extractNameFromEmail = (email: string) =>
	email
		.split('@')[0]
		.replace(/[._-]/g, ' ')
		.replace(/\b\w/g, (c) => c.toUpperCase())
