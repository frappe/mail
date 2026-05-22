<template>
	<router-link
		:to="{
			name: 'Mail',
			params: { accountId: $route.params.accountId, mailbox, threadID: mail.thread_id },
			query: $route.query,
		}"
		class="sm:hover:bg-surface-gray-1 group flex cursor-default select-none space-x-2.5 border-b px-3.5 py-2.5 sm:space-x-5 sm:px-5"
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
			class="flex shrink-0 items-center justify-center max-sm:w-10"
			:class="isFullWidth ? 'h-8' : 'h-10 sm:-mt-1.5'"
		>
			<div
				v-if="!isMobile"
				class="checkbox-hitbox -m-3 cursor-pointer p-3"
				@click.stop.prevent="emit('setSelected', !isSelected)"
			>
				<Checkbox :model-value="isSelected" size="md" class="pointer-events-none" />
			</div>
			<div
				v-else-if="isSelected"
				class="bg-surface-gray-7 hitbox flex h-8 w-8 shrink-0 rounded-full"
				@click.stop.prevent="emit('setSelected', false)"
			>
				<Check class="text-ink-white m-auto h-5 w-5 stroke-[3px]" />
			</div>
			<Avatar
				v-show="!isSelected && isMobile"
				:label="getFirstAlphabet(mail.from_name) || getFirstAlphabet(mail.from_email)"
				:image="mail.user_image"
				size="xl"
				class="hitbox"
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
				<div class="mr-2 mt-0.5 flex items-center space-x-1.5 truncate">
					<span v-if="!mail.seen" class="min-h-2 min-w-2 rounded-full bg-blue-500" />
					<h3
						class="truncate text-[15px] !font-medium sm:text-base"
						:class="{ '!font-semibold': !mail.seen }"
					>
						{{ header }}
					</h3>
					<Badge v-if="mail.draft" size="sm" :label="__('Draft')" theme="red" />
				</div>
				<MailDate v-if="!isFullWidth" :datetime="mail.received_at" :in-list="true" />
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
			<div
				class="flex items-center justify-between truncate"
				:class="{ 'min-w-0 flex-1 !text-base': isFullWidth }"
			>
				<h5
					class="text-ink-gray-5 truncate text-sm !leading-[1.5]"
					:class="{ italic: !mail.preview }"
				>
					{{ mail.preview || __('— No message body —') }}
				</h5>

				<div v-if="!isFullWidth" class="ml-3.5 flex space-x-3.5">
					<MailListItemActions
						:is-hovered
						:mail
						@set-seen="(seen: boolean) => emit('setSeen', seen)"
						@archive-thread="emit('archiveThread')"
						@trash-thread="emit('trashThread')"
						@delete-thread="emit('deleteThread')"
						@set-flagged="(flagged: boolean) => emit('setFlagged', flagged)"
					/>
				</div>
			</div>
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
		<div v-if="isFullWidth" class="flex w-32 shrink-0 items-center justify-end space-x-4">
			<MailDate v-if="!isHovered" :datetime="mail.received_at" :in-list="true" />
			<MailListItemActions
				:is-hovered
				:mail
				@set-seen="(seen: boolean) => emit('setSeen', seen)"
				@archive-thread="emit('archiveThread')"
				@trash-thread="emit('trashThread')"
				@delete-thread="emit('deleteThread')"
				@set-flagged="(flagged: boolean) => emit('setFlagged', flagged)"
			/>
		</div>
		<AttachmentViewer
			v-model="showAttachmentViewer"
			:attachments="mail.attachments"
			:initial-index="attachmentIndex"
		/>
	</router-link>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { Check, Download, Loader } from 'lucide-vue-next'
import { Avatar, Badge, Checkbox, Popover, Tooltip } from 'frappe-ui'

import { getAttachmentUrl } from '@/resources'
import { downloadUrlAsFile, getFileIcon, getFirstAlphabet, getFormattedRecipients } from '@/utils'
import { useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'
import AttachmentCapsule from '@/components/AttachmentCapsule.vue'
import AttachmentViewer from '@/components/AttachmentViewer.vue'
import MailDate from '@/components/MailDate.vue'
import MailListItemActions from '@/components/MailListItemActions.vue'

import type { Attachment, Thread } from '@/types'

const { mailbox, mail, isSelected } = defineProps<{
	mailbox: string
	mail: Thread
	isSelected: boolean
}>()

const emit = defineEmits([
	'setSeen',
	'archiveThread',
	'trashThread',
	'deleteThread',
	'setFlagged',
	'setSelected',
])

const user = inject('$user')
const { isMobile } = useScreenSize()
const { mailboxIds } = userStore()

const mailboxes = computed(() => mail.mailboxes.map((m) => m.mailbox_id))

const attachments = computed(
	() => mail.attachments.filter((m) => m.filename && m.disposition === 'attachment') || [],
)

const isFullWidth = computed(() => !(user.data.show_reading_pane || isMobile.value))

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

	downloadUrlAsFile(url, attachment.filename || 'attachment')
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

<style scoped>
.hitbox {
	@apply relative after:absolute after:-inset-2 after:content-[''];
}

.checkbox-hitbox:hover :deep(input[type='checkbox']) {
	@apply border-outline-gray-5 shadow-sm;
}
</style>
