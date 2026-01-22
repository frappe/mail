<template>
	<div
		class="group/capsule hover:border-outline-gray-3 flex cursor-pointer items-center space-x-2 rounded-full border px-2 py-1.5"
	>
		<div class="text-ink-gray-4">
			<Loader v-if="isDownloading" class="h-4 w-4 shrink-0 animate-spin" />
			<template v-else>
				<component
					:is="getFileIcon(type)"
					class="h-4 w-4 shrink-0"
					:class="{ 'group-hover/capsule:hidden': blobID }"
				/>
				<button
					class="hidden"
					:class="{ 'group-hover/capsule:block': blobID }"
					@click.stop.prevent="downloadAttachment"
				>
					<Download class="hover:text-ink-gray-8 h-4 w-4 shrink-0" />
				</button>
			</template>
		</div>
		<span class="truncate text-sm">{{ fileName }}</span>
	</div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Download, Loader } from 'lucide-vue-next'
import { createResource } from 'frappe-ui'

import { getFileIcon, raiseToast } from '@/utils'

const { fileName, blobID, type } = defineProps<{
	fileName: string
	blobID?: string
	type?: string
}>()

const isDownloading = ref(false)

const downloadAttachment = async () => {
	if (!blobID) return
	isDownloading.value = true
	await fetchAttachment.submit()
	isDownloading.value = false
}

const fetchAttachment = createResource({
	url: 'mail.api.mail.fetch_attachment',
	makeParams: () => ({ blob_id: blobID }),
	onSuccess: (data: number[]) => {
		const byteArray = new Uint8Array(data)
		const blob = new Blob([byteArray], { type })
		const url = URL.createObjectURL(blob)

		const link = document.createElement('a')
		link.href = url
		link.download = fileName || 'attachment'
		document.body.appendChild(link)
		link.click()
		document.body.removeChild(link)
		URL.revokeObjectURL(url)
	},
	onError: (error) => raiseToast(error.message, 'error'),
	cache: ['attachment-download', blobID],
})
</script>
