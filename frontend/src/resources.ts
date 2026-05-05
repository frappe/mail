import { createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

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
