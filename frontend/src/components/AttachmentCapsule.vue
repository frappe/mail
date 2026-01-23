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
					:class="{ 'sm:group-hover/capsule:hidden': blobID }"
				/>
				<button
					class="hidden"
					:class="{ 'sm:group-hover/capsule:block': blobID }"
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

import { getAttachmentUrl } from '@/resources'
import { getFileIcon } from '@/utils'

const { fileName, blobID, type } = defineProps<{
	fileName: string
	blobID?: string
	type?: string
}>()

const isDownloading = ref(false)

const downloadAttachment = async () => {
	if (!blobID) return

	isDownloading.value = true
	const url = await getAttachmentUrl(blobID, type)
	const link = document.createElement('a')
	link.href = url
	link.download = fileName || 'attachment'
	document.body.appendChild(link)
	link.click()
	document.body.removeChild(link)
	URL.revokeObjectURL(url)
	isDownloading.value = false
}
</script>
