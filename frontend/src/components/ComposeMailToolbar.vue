<template>
	<FileUploader
		:class="{ 'fixed left-0 right-0 z-20': isMobile }"
		:style="{ bottom: toolbarBottom }"
		:upload-args="{ private: true, folder: 'Home/Frappe Mail' }"
		@success="(file) => emit('addAttachment', { ...file, disposition: 'attachment' })"
	>
		<template #default="{ file, progress, uploading, openFileSelector, error }">
			<div
				v-if="uploading"
				class="bg-surface-gray-2 text-ink-gray-6 mb-2 rounded p-2.5 text-sm"
			>
				<div class="mb-1.5 flex items-center">
					<span class="mr-1 font-medium"> {{ file.name }} </span>
					<span class="font-extralight"> ({{ formatBytes(file.size) }}) </span>
				</div>
				<Progress :value="progress" />
			</div>

			<ErrorMessage :message="error" class="mb-2.5" />

			<div
				class="flex flex-wrap justify-between gap-2 overflow-hidden border-t pt-2.5"
				:class="{ 'pb-2.5': isMobile }"
			>
				<!-- Text editor buttons -->
				<div class="flex items-center gap-1 overflow-x-auto" :class="{ 'px-3': isMobile }">
					<TextEditorFixedMenu :buttons class="!bg-inherit" />
					<EmojiPicker
						v-if="!isMobile"
						v-slot="{ togglePopover }"
						@update:model-value="emit('appendEmoji', $event)"
					>
						<Button variant="ghost" class="max-h-6 max-w-6" @click="togglePopover()">
							<template #icon>
								<Laugh class="h-4 w-4" />
							</template>
						</Button>
					</EmojiPicker>
					<Button variant="ghost" class="max-h-6 max-w-6" @click="openFileSelector()">
						<template #icon>
							<Paperclip class="h-4 w-4" />
						</template>
					</Button>
				</div>

				<!-- Send & Discard -->
				<div v-if="!isMobile" class="ml-auto flex items-center space-x-2">
					<span v-if="isSavingDraft" class="text-ink-gray-5 text-base italic">
						{{ __('Saving Draft...') }}
					</span>
					<template v-else>
						<Button
							:label="__('Discard')"
							:icon-left="Trash2"
							:disabled="isLoading"
							@click="emit('discardMail')"
						/>
						<Button
							variant="solid"
							:label="__('Send')"
							:icon-left="SendHorizontal"
							:disabled="isRecipientsEmpty || isLoading"
							@click="emit('sendMail')"
						/>
					</template>
				</div>
			</div>
		</template>
	</FileUploader>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Laugh, Paperclip, SendHorizontal, Trash2 } from 'lucide-vue-next'
import { Button, ErrorMessage, FileUploader, Progress, TextEditorFixedMenu } from 'frappe-ui'

import { formatBytes } from '@/utils'
import { useScreenSize, useTextEditorButtons } from '@/utils/composables'
import EmojiPicker from '@/components/EmojiPicker.vue'

const { isSavingDraft, isLoading, isRecipientsEmpty } = defineProps<{
	isSavingDraft: boolean
	isLoading: boolean
	isRecipientsEmpty: boolean
}>()

const emit = defineEmits(['appendEmoji', 'addAttachment', 'discardMail', 'sendMail'])

// Make toolbar hover over keyboard on mobile

const { isMobile } = useScreenSize()
const { buttons } = useTextEditorButtons()

const toolbarBottom = ref('0px')

const updatePosition = () => {
	if (window.visualViewport)
		toolbarBottom.value =
			window.innerHeight -
			window.visualViewport.height -
			window.visualViewport.offsetTop +
			'px'
}

onMounted(() => {
	if (!window.visualViewport) return
	window.visualViewport.addEventListener('resize', updatePosition)
	window.visualViewport.addEventListener('scroll', updatePosition)

	updatePosition()

	onUnmounted(() => {
		if (!window.visualViewport) return
		window.visualViewport.removeEventListener('resize', updatePosition)
		window.visualViewport.removeEventListener('scroll', updatePosition)
	})
})
</script>
