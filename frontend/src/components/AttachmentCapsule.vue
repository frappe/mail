<template>
	<button
		class="flex items-center space-x-2 rounded-full border px-2 py-1.5"
		:class="{ 'hover:border-outline-gray-3 cursor-pointer': blobID }"
		@click="openAttachment"
	>
		<Paperclip class="text-ink-gray-4 h-3.5 min-h-3.5 w-3.5 min-w-3.5" />
		<span class="truncate text-sm">{{ fileName }}</span>

		<AttachmentViewer
			v-model="showViewer"
			:attachments="[{ fileName, blobID: blobID!, type }]"
			:initial-index="0"
		/>
	</button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Paperclip } from 'lucide-vue-next'

import AttachmentViewer from '@/components/AttachmentViewer.vue'

const { fileName, blobID, type } = defineProps<{
	fileName: string
	blobID?: string
	type?: string
}>()

const showViewer = ref(false)

const openAttachment = () => {
	if (blobID) showViewer.value = true
}
</script>
