import { createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'
import type { Attachment } from '@/types'

const store = userStore()

export const fetchAttachment = createResource({
	url: 'mail.api.mail.fetch_attachment',
	makeParams: (blobID: string) => ({ account: store.account, blob_id: blobID }),
	onError: (error) => raiseToast(error.message, 'error'),
	cache: ['attachment'],
})

export const getAttachmentUrl = async (blobID: string, type?: string) => {
	const attachment = await fetchAttachment.submit(blobID)
	const byteArray = new Uint8Array(attachment)
	const blob = new Blob([byteArray], { type })
	return URL.createObjectURL(blob)
}

export const fetchAttachmentsAsZip = createResource({
	url: 'mail.api.mail.fetch_attachments_as_zip',
	makeParams: (attachments: Attachment[]) => ({
		account: store.account,
		attachments: JSON.stringify(
			attachments.map((a) => ({ blob_id: a.blob_id, filename: a.filename })),
		),
	}),
	onError: (error) => raiseToast(error.message, 'error'),
})

export const getAttachmentsZipUrl = async (attachments: Attachment[]) => {
	const zip = await fetchAttachmentsAsZip.submit(attachments)
	const byteArray = new Uint8Array(zip)
	const blob = new Blob([byteArray], { type: 'application/zip' })
	return URL.createObjectURL(blob)
}
