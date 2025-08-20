import { toast } from 'frappe-ui'

import dayjs from '@/utils/dayjs'

import type { Recipient } from '@/types'

export const convertToTitleCase = (str: string) =>
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
	const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']

	const i = Math.floor(Math.log(bytes) / Math.log(k))

	return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))}${sizes[i]}`
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

export const kebabToTitleCase = (str: string) =>
	str
		.split('-')
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(' ')

export const copyToClipBoard = async (text: string) => {
	try {
		await navigator.clipboard.writeText(text)
		raiseToast(__('Message copied successfully!'))
	} catch {
		raiseToast(__('Failed to copy text.'), 'error')
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

export const getFormattedDate = (date: Date) => {
	if (dayjs(date).isToday()) return __('Today')
	if (dayjs(date).isYesterday()) return __('Yesterday')
	const isCurrentYear = dayjs(date).year() === dayjs().year()
	return dayjs(date).format(isCurrentYear ? 'D MMMM' : 'D MMMM YYYY')
}

export const textEditorButtons = [
	'Paragraph',
	['Heading 2', 'Heading 3', 'Heading 4', 'Heading 5', 'Heading 6'],
	'Separator',
	'Bold',
	'Italic',
	'FontColor',
	'Separator',
	'Align Left',
	'Align Center',
	'Align Right',
	'Separator',
	'Bullet List',
	'Numbered List',
	'Separator',
	'Image',
	'Link',
]

export const getFirstAlphabet = (str?: string) => str?.match(/[A-Za-z]/)?.[0]

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
