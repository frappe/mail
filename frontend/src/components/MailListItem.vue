<template>
	<div
		class="sm:hover:bg-surface-gray-1 flex cursor-pointer space-x-2.5 border-b px-3.5 py-2.5 sm:px-5"
		:class="{
			'!bg-surface-blue-1': isSelected || isTouching,
			'!py-2': isFullWidth,
			'select-none': isMobile,
		}"
		@mouseenter="isHovered = true"
		@mouseleave="isHovered = false"
		@touchstart="onTouchStart"
		@touchend="clearTouchTimer"
		@touchcancel="clearTouchTimer"
	>
		<div class="flex h-10 min-h-10 w-10 min-w-10 items-center justify-center">
			<Checkbox
				v-if="(isHovered || isSelected) && !isMobile"
				v-model="isSelected"
				size="md"
				@click.stop="isManuallySelected = true"
			/>
			<div
				v-else-if="isSelected && isMobile"
				class="bg-surface-gray-3 flex h-10 min-h-10 w-10 min-w-10 rounded-full"
				@click.stop="isSelected = false"
			>
				<Check class="text-ink-gray-5 m-auto h-5 w-5" />
			</div>
			<Avatar
				v-else
				:label="getFirstAlphabet(mail.from_name) || getFirstAlphabet(mail.from_email)"
				:size="isFullWidth ? 'lg' : '2xl'"
				@click.stop="isSelected = true"
			/>
		</div>

		<div
			class="grow truncate"
			:class="isFullWidth ? 'flex items-center space-x-3' : 'space-y-1'"
		>
			<div
				class="flex items-center"
				:class="isFullWidth ? 'min-w-48 max-w-48' : 'justify-between'"
			>
				<h3 class="mr-1 mt-0.5 flex items-center truncate">
					<span
						v-if="!mail.seen"
						class="mr-1.5 min-h-2 min-w-2 rounded-full bg-blue-500"
					/>
					<span class="truncate text-base font-semibold">
						{{ header }}
					</span>
				</h3>
				<MailDate
					v-if="!isFullWidth && !isHovered"
					:datetime="mail.received_at"
					:in-list="true"
				/>
			</div>
			<h4
				class="truncate text-sm leading-[1.5]"
				:class="{ italic: !mail.subject, '!text-base': isFullWidth }"
			>
				{{ mail.subject || __('[No subject]') }}
			</h4>
			<h5
				class="text-ink-gray-6 truncate text-sm leading-[1.5]"
				:class="{ italic: !mail.preview, 'min-w-0 flex-1 !text-base': isFullWidth }"
			>
				{{ mail.preview || __('— No message body —') }}
			</h5>
			<div
				v-if="mail.attachments || mail.draft"
				class="flex items-center"
				:class="{ 'ml-auto min-w-fit': isFullWidth }"
			>
				<AttachmentCapsule
					v-for="(attachment, idx) in mail.attachments?.slice(0, 2)"
					:key="idx"
					:file-name="attachment.filename"
					:blob-i-d="attachment.blob_id"
					:type="attachment.type"
					class="mr-2 max-w-32"
					@click.stop.prevent
				/>
				<AttachmentCapsule
					v-if="mail.attachments?.length > 2"
					:file-name="__('+{0} more', [String(mail.attachments.length - 2)])"
				/>
				<Badge
					v-if="mail.draft"
					class="ml-auto"
					:class="{ invisible: !isFullWidth && isHovered }"
					:label="__('Draft')"
					theme="red"
				/>
			</div>
			<div v-if="isFullWidth && !isHovered" class="flex w-20 shrink-0 justify-end">
				<MailDate :datetime="mail.received_at" :in-list="true" />
			</div>
		</div>
		<div
			v-if="isHovered && !isMobile"
			class="flex items-center justify-end space-x-2"
			:class="{ 'w-[82px] shrink-0': isFullWidth }"
		>
			<Tooltip v-for="action in actions" :key="action.label" :text="action.label">
				<Button variant="ghost" @click.stop="action.onClick">
					<template #icon>
						<component :is="action.icon" class="text-ink-gray-5 h-4 w-4" />
					</template>
				</Button>
			</Tooltip>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, Mail, MailOpen, Trash2 } from 'lucide-vue-next'
import { Avatar, Badge, Button, Checkbox, Tooltip } from 'frappe-ui'

import { getFirstAlphabet } from '@/utils'
import { useScreenSize } from '@/utils/composables'
import AttachmentCapsule from '@/components/AttachmentCapsule.vue'
import MailDate from '@/components/MailDate.vue'

import type { LayoutType, Thread } from '@/types'

const { mail, userLayout } = defineProps<{ mail: Thread; userLayout: LayoutType }>()

const emit = defineEmits([
	'select-thread',
	'deselect-thread',
	'setSeen',
	'trashThread',
	'deleteThread',
])

const { isMobile } = useScreenSize()

const isFullWidth = computed(() => userLayout === 'full' && !isMobile.value)

const header = computed(() => {
	const isOutgoing = ['sent', 'drafts'].includes(mail.mailbox_role)
	if (isOutgoing)
		return __('To: {0}', [mail.recipients.map((d) => d.name || d.email).join(', ')])
	return mail.from_name || mail.from_email
})

const isHovered = ref(false)
const isSelected = ref(false)
const isManuallySelected = ref(false)

watch(isSelected, () => {
	emit(isSelected.value ? 'select-thread' : 'deselect-thread', isManuallySelected.value)
	isManuallySelected.value = false
})

const setIsSelected = (value: boolean) => (isSelected.value = value)

defineExpose({ id: mail.thread_id, setIsSelected })

const actions = computed(() =>
	[
		{
			label: __('Mark as Unread'),
			onClick: () => emit('setSeen', false),
			icon: Mail,
			condition: mail.seen,
		},
		{
			label: __('Mark as Read'),
			onClick: () => emit('setSeen', true),
			icon: MailOpen,
			condition: !mail.seen,
		},
		{
			label: __('Move to Trash'),
			onClick: () => emit('trashThread'),
			icon: Trash2,
			condition: mail.mailbox_role !== 'trash',
		},
		{
			label: __('Delete Message'),
			onClick: () => emit('deleteThread'),
			icon: Trash2,
			condition: mail.mailbox_role === 'trash',
		},
	].filter((action) => action.condition),
)

// touch

let touchStartX = 0
let touchStartY = 0
let touchMoved = false
let touchTimer: ReturnType<typeof setTimeout> | null = null

const isTouching = ref(false)

const onTouchStart = (e: TouchEvent) => {
	touchMoved = false
	touchStartX = e.touches[0].clientX
	touchStartY = e.touches[0].clientY
	isTouching.value = true
	document.addEventListener('touchmove', onTouchMove, { passive: true })

	touchTimer = setTimeout(() => {
		if (!touchMoved) isSelected.value = !isSelected.value
	}, 450)
}

const clearTouchTimer = () => {
	isTouching.value = false
	document.removeEventListener('touchmove', onTouchMove)

	if (touchTimer) {
		clearTimeout(touchTimer)
		touchTimer = null
	}
}

const onTouchMove = (e: TouchEvent) => {
	const touch = e.touches[0]
	const dx = Math.abs(touch.clientX - touchStartX)
	const dy = Math.abs(touch.clientY - touchStartY)
	if (dx > 10 || dy > 10) {
		touchMoved = true
		clearTouchTimer()
	}
}
</script>
