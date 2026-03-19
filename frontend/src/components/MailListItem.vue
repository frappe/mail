<template>
	<router-link
		:to="{ name: 'Mail', params: { mailbox, threadID: mail.thread_id }, query: $route.query }"
		class="sm:hover:bg-surface-gray-1 group flex cursor-pointer select-none space-x-2.5 border-b px-3.5 py-2.5 sm:px-5"
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
		<div
			class="flex w-10 shrink-0 items-center justify-center"
			:class="isFullWidth ? 'h-8' : 'h-10'"
		>
			<Checkbox
				v-if="(isHovered || isSelected) && !isMobile"
				:model-value="isSelected"
				size="md"
				class="-ml-[1px]"
				@update:model-value="emit('setSelected', $event)"
				@click.stop
			/>
			<div
				v-else-if="isSelected && isMobile"
				class="bg-surface-gray-3 flex h-10 min-h-10 w-10 min-w-10 rounded-full"
				@click.stop.prevent="emit('setSelected', false)"
			>
				<Check class="text-ink-gray-5 m-auto h-5 w-5" />
			</div>
			<Avatar
				v-show="!isSelected && (!isHovered || isMobile)"
				:label="getFirstAlphabet(mail.from_name) || getFirstAlphabet(mail.from_email)"
				:image="mail.user_image"
				:size="isFullWidth ? 'lg' : '2xl'"
				@click.stop.prevent="emit('setSelected', true)"
			/>
		</div>

		<div
			class="grow truncate"
			:class="isFullWidth ? 'flex items-center space-x-3' : 'space-y-1'"
		>
			<div
				class="flex items-center"
				:class="isFullWidth ? 'w-48 shrink-0' : 'justify-between'"
			>
				<h3 class="mr-1 mt-0.5 flex items-center truncate">
					<span
						v-if="!mail.seen"
						class="mr-1.5 min-h-2 min-w-2 rounded-full bg-blue-500"
					/>
					<span
						class="truncate text-[15px] sm:text-base"
						:class="{ '!font-semibold': !mail.seen }"
					>
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
				class="truncate text-sm !leading-[1.5]"
				:class="{
					italic: !mail.subject,
					'!text-base': isFullWidth,
					'!font-semibold': !mail.seen,
				}"
			>
				{{ mail.subject || __('[No subject]') }}
			</h4>
			<h5
				class="text-ink-gray-5 truncate text-sm !leading-[1.5]"
				:class="{ italic: !mail.preview, 'min-w-0 flex-1 !text-base': isFullWidth }"
			>
				{{ mail.preview || __('— No message body —') }}
			</h5>
			<div
				v-if="attachments.length || mail.draft || ['starred', 'search'].includes(mailbox)"
				class="flex items-center"
				:class="{ 'ml-auto min-w-fit': isFullWidth }"
			>
				<Tooltip
					v-for="(attachment, idx) in attachments.slice(0, 2)"
					:key="idx"
					:text="attachment.filename"
				>
					<AttachmentCapsule
						:file-name="attachment.filename"
						:blob-i-d="attachment.blob_id"
						:type="attachment.type"
						class="mr-2"
						:class="isFullWidth ? 'max-w-32' : 'max-w-20'"
						@click.stop.prevent="openAttachment(idx)"
					/>
				</Tooltip>
				<Popover v-if="attachments.length > 2" placement="bottom">
					<template #target="{ togglePopover }">
						<Tooltip :text="__('View remaining attachments')">
							<AttachmentCapsule
								:file-name="`+${String(attachments.length - 2)}`"
								class="mr-2"
								@click.stop.prevent="togglePopover()"
							/>
						</Tooltip>
					</template>
					<template #body-main>
						<div class="max-h-80 overflow-y-auto p-1">
							<Tooltip
								v-for="(attachment, idx) in attachments.slice(2)"
								:key="idx"
								:text="attachment.filename"
							>
								<div
									class="group/capsule hover:bg-surface-gray-1 flex max-w-60 cursor-pointer space-x-2 truncate rounded px-2 py-1.5"
									@click.stop.prevent="openAttachment(idx + 2)"
								>
									<div class="text-ink-gray-4">
										<Loader
											v-if="
												currentlyDownloading.includes(attachment.blob_id)
											"
											class="h-4 w-4 shrink-0 animate-spin"
										/>
										<template v-else>
											<component
												:is="getFileIcon(attachment.type)"
												class="h-4 w-4 shrink-0 sm:group-hover/capsule:hidden"
											/>
											<button
												class="hidden sm:group-hover/capsule:block"
												@click.stop.prevent="
													downloadAttachment(attachment)
												"
											>
												<Download
													class="hover:text-ink-gray-8 h-4 w-4 shrink-0"
												/>
											</button>
										</template>
									</div>
									<span class="truncate text-sm">{{ attachment.filename }}</span>
								</div>
							</Tooltip>
						</div>
					</template>
				</Popover>
				<Badge
					v-if="mail.draft"
					class="ml-auto"
					:class="{ invisible: !isFullWidth && isHovered }"
					:label="__('Draft')"
					theme="red"
				/>
				<template v-if="isFullWidth && ['starred', 'search'].includes(mailbox)">
					<div
						v-for="m in mail.mailboxes"
						:key="m.mailbox_id"
						class="bg-surface-gray-2 group-hover:bg-surface-gray-3 inline-flex rounded p-1.5 text-xs"
					>
						{{ m.mailbox_name }}
					</div>
				</template>
			</div>
			<div v-if="isFullWidth && !isHovered" class="flex w-20 shrink-0 justify-end">
				<MailDate :datetime="mail.received_at" :in-list="true" />
			</div>
			<template v-if="!isFullWidth && ['starred', 'search'].includes(mailbox)">
				<div
					v-for="m in mail.mailboxes"
					:key="m.mailbox_id"
					class="bg-surface-gray-2 group-hover:bg-surface-gray-3 mr-1.5 inline-flex rounded p-1.5 text-xs"
				>
					{{ m.mailbox_name }}
				</div>
			</template>
		</div>
		<div
			v-if="isHovered && !isMobile"
			class="flex items-center justify-end space-x-2"
			:class="{ 'w-[82px] shrink-0': isFullWidth }"
		>
			<Button
				v-for="action in actions"
				:key="action.label"
				:tooltip="action.label"
				variant="ghost"
				@click.stop.prevent="action.onClick"
			>
				<template #icon>
					<component :is="action.icon" class="text-ink-gray-5 h-4 w-4" />
				</template>
			</Button>
		</div>
		<AttachmentViewer
			v-model="showAttachmentViewer"
			:attachments="mail.attachments"
			:initial-index="attachmentIndex"
		/>
	</router-link>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, Download, Loader, Mail, MailOpen, Trash2 } from 'lucide-vue-next'
import { Avatar, Badge, Button, Checkbox, Popover, Tooltip } from 'frappe-ui'

import { getAttachmentUrl } from '@/resources'
import { getFileIcon, getFirstAlphabet, getFormattedRecipients } from '@/utils'
import { useLayout, useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'
import AttachmentCapsule from '@/components/AttachmentCapsule.vue'
import AttachmentViewer from '@/components/AttachmentViewer.vue'
import MailDate from '@/components/MailDate.vue'

import type { Attachment, Thread } from '@/types'

const { mailbox, mail, isSelected } = defineProps<{
	mailbox: string
	mail: Thread
	isSelected: boolean
}>()

const emit = defineEmits(['setSeen', 'trashThread', 'deleteThread', 'setSelected'])

const { isMobile } = useScreenSize()
const { showReadingPane } = useLayout()
const { mailboxIds } = userStore()

const mailboxes = computed(() => mail.mailboxes.map((m) => m.mailbox_id))

const attachments = computed(
	() => mail.attachments.filter((m) => m.filename && m.disposition === 'attachment') || [],
)

const isFullWidth = computed(() => !(showReadingPane.value || isMobile.value))

const header = computed(() => {
	const isOutgoing =
		mailboxes.value.includes(mailboxIds.sent) || mailboxes.value.includes(mailboxIds.drafts)

	return isOutgoing
		? getFormattedRecipients(mail.recipients) || __('To:')
		: mail.from_name || mail.from_email
})

const isHovered = ref(false)

const showAttachmentViewer = ref(false)
const attachmentIndex = ref(0)

const openAttachment = (idx: number) => {
	attachmentIndex.value = idx
	showAttachmentViewer.value = true
}

defineExpose({ id: mail.thread_id })

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
			condition: !mailboxes.value.includes(mailboxIds.trash),
		},
		{
			label: __('Delete Thread'),
			onClick: () => emit('deleteThread'),
			icon: Trash2,
			condition: mailboxes.value.includes(mailboxIds.trash),
		},
	].filter((action) => action.condition),
)

// attachment

const currentlyDownloading = ref<string[]>([])

const downloadAttachment = async (attachment: Attachment) => {
	currentlyDownloading.value.push(attachment.blob_id)
	const url = await getAttachmentUrl(attachment.blob_id, attachment.type)
	if (!url) {
		currentlyDownloading.value = currentlyDownloading.value.filter(
			(id) => id !== attachment.blob_id,
		)
		return
	}

	const link = document.createElement('a')
	link.href = url
	link.download = attachment.filename || 'attachment'
	document.body.appendChild(link)
	link.click()
	document.body.removeChild(link)
	URL.revokeObjectURL(url)
	currentlyDownloading.value = currentlyDownloading.value.filter(
		(id) => id !== attachment.blob_id,
	)
}

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
		if (!touchMoved) emit('setSelected', !isSelected)
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
