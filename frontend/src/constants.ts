export const getAttachmentOptions = () => [
	{ label: __('All'), value: ' ' },
	{ label: __('With Attachments'), value: 'true' },
	{ label: __('Without Attachments'), value: 'false' },
]

export const getReadStatusOptions = () => [
	{ label: __('All'), value: ' ' },
	{ label: __('Read'), value: 'true' },
	{ label: __('Unread'), value: 'false' },
]

export const FOLDER_ICON_MAP = {
	inbox: 'inbox',
	sent: 'send',
	trash: 'trash-2',
	junk: 'mail-warning',
	drafts: 'pencil-line',
	archive: 'archive',
	important: 'bookmark',
}

export const FOLDER_COLOR_MAP = {
	Gray: 'bg-surface-gray-5',
	Blue: 'bg-blue-500',
	Green: 'bg-green-500',
	Amber: 'bg-amber-500',
	Red: 'bg-red-500',
	Purple: 'bg-purple-500',
}
