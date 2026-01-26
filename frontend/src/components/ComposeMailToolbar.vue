<template>
	<div :class="{ 'fixed left-0 right-0 z-20': isMobile }" :style="{ bottom: toolbarBottom }">
		<div
			class="flex flex-wrap justify-between gap-2 overflow-hidden pt-2.5"
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
				<Button variant="ghost" class="max-h-6 max-w-6" @click="fileInput?.click()">
					<template #icon>
						<Paperclip class="h-4 w-4" />
					</template>
				</Button>
				<input
					ref="fileInput"
					type="file"
					class="hidden"
					multiple
					@change="onFilesSelected"
				/>
			</div>

			<!-- Send & Discard -->
			<div v-if="!isMobile" class="ml-auto flex items-center space-x-2">
				<span v-if="isSavingDraft" class="text-ink-gray-5 text-base italic">
					{{ __('Saving Draft...') }}
				</span>
				<Button
					:label="__('Discard')"
					:tooltip="__('Discard ({0}+D)', [modifier])"
					:icon-left="Trash2"
					@click="emit('discardMail')"
				/>
				<Popover @open="initScheduleDateTime" placement="top-end">
					<template #target="{ togglePopover, isOpen }">
						<Button
							:label="__('Schedule')"
							:tooltip="__('Schedule send')"
							:icon-left="CalendarClock"
							:class="{ 'ring-2 ring-blue-300': isOpen }"
							@click="togglePopover()"
						/>
					</template>
					<template #body="{ close }">
						<div class="rounded-lg bg-surface-white shadow-xl border border-outline-gray-1 p-4 w-72 mb-2">
							<div class="mb-3 text-sm font-medium text-ink-gray-7">{{ __('Schedule Send') }}</div>
							<div class="flex justify-end space-x-2 mb-3">
								<Button :label="__('Cancel')" @click="close()" />
								<Button
									variant="solid"
									:label="__('Schedule')"
									:disabled="!isValidScheduleTime"
									@click="onScheduleSend(close)"
								/>
							</div>
							<FormControl
								v-model="scheduledDateTime"
								type="datetime-local"
								:min="minDateTime"
								variant="outline"
							/>
							<!-- Space for native calendar dropdown -->
							<div class="h-52"></div>
						</div>
					</template>
				</Popover>
				<Button
					variant="solid"
					:label="__('Send')"
					:tooltip="__('Send ({0}+Enter)', [modifier])"
					:icon-left="SendHorizontal"
					:disabled="isRecipientsEmpty"
					@click="emit('sendMail')"
				/>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import { CalendarClock, Laugh, Paperclip, SendHorizontal, Trash2 } from 'lucide-vue-next'
import { Button, FormControl, Popover, TextEditorFixedMenu } from 'frappe-ui'

import { isMac } from '@/utils'
import { useScreenSize, useTextEditorButtons, useVisualViewport } from '@/utils/composables'
import EmojiPicker from '@/components/EmojiPicker.vue'

const { isSavingDraft, isRecipientsEmpty } = defineProps<{
	isSavingDraft: boolean
	isRecipientsEmpty: boolean
}>()

const emit = defineEmits(['appendEmoji', 'selectFiles', 'discardMail', 'sendMail', 'scheduleMail'])

const modifier = computed(() => (isMac ? '⌘' : 'Ctrl'))

// Schedule send state
const scheduledDateTime = ref('')

// Format datetime to local datetime-local input format (YYYY-MM-DDTHH:mm)
const formatToLocalDatetime = (date: Date): string => {
	const year = date.getFullYear()
	const month = String(date.getMonth() + 1).padStart(2, '0')
	const day = String(date.getDate()).padStart(2, '0')
	const hours = String(date.getHours()).padStart(2, '0')
	const minutes = String(date.getMinutes()).padStart(2, '0')
	return `${year}-${month}-${day}T${hours}:${minutes}`
}

// Minimum datetime is current local time (prevents scheduling in the past)
const minDateTime = computed(() => formatToLocalDatetime(new Date()))

// Initialize with default time (1 hour from now, rounded to next 30 min)
const initScheduleDateTime = () => {
	const now = new Date()
	now.setHours(now.getHours() + 1)
	// Round to next 30 minutes
	const minutes = now.getMinutes()
	now.setMinutes(minutes < 30 ? 30 : 60)
	now.setSeconds(0)
	now.setMilliseconds(0)
	scheduledDateTime.value = formatToLocalDatetime(now)
}

// Validate that scheduled time is in the future
const isValidScheduleTime = computed(() => {
	if (!scheduledDateTime.value || isRecipientsEmpty) return false
	const scheduled = new Date(scheduledDateTime.value)
	return scheduled > new Date()
})

const onScheduleSend = (close: () => void) => {
	if (scheduledDateTime.value && isValidScheduleTime.value) {
		// Convert local datetime to ISO string for API
		const localDate = new Date(scheduledDateTime.value)
		emit('scheduleMail', localDate.toISOString())
		scheduledDateTime.value = ''
		close()
	}
}

// Make toolbar hover over keyboard on mobile

const { isMobile } = useScreenSize()
const { buttons } = useTextEditorButtons()

const toolbarBottom = useVisualViewport(
	(viewport) => `${window.innerHeight - viewport.height - viewport.offsetTop}px`,
)

const fileInput = useTemplateRef('fileInput')

const onFilesSelected = async (e: Event) => {
	const input = e.target as HTMLInputElement
	const files = Array.from(input.files ?? [])
	if (!files.length) return

	emit('selectFiles', files)
	input.value = ''
}
</script>

<!-- todo: file upload -> discard race condition (draft saved) -->
