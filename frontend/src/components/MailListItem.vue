<template>
	<div
		class="flex cursor-pointer space-x-2.5 border-b px-3.5 py-2.5 sm:px-5 sm:hover:bg-gray-50"
		:class="{ '!bg-blue-50': isSelected, '!py-2': isFullWidth }"
		@mouseenter="isHovered = true"
		@mouseleave="isHovered = false"
	>
		<div class="flex h-8 min-h-8 min-w-8 items-center justify-center">
			<Checkbox
				v-if="isHovered || isSelected"
				v-model="isSelected"
				size="md"
				@click.stop="isManuallySelected = true"
			/>
			<Avatar
				v-else
				:label="mail.from_name || mail.from_email"
				:size="isFullWidth ? 'lg' : 'xl'"
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
				<MailDate v-if="!isFullWidth" :datetime="mail.received_at" :in-list="true" />
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
					:class="isFullWidth ? 'ml-5' : 'ml-auto'"
					:label="__('Draft')"
					theme="red"
				/>
			</div>
			<div v-if="isFullWidth" class="flex min-w-20 max-w-20 justify-end">
				<MailDate :datetime="mail.received_at" :in-list="true" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Avatar, Badge, Checkbox } from 'frappe-ui'

import { useScreenSize } from '@/utils/composables'
import AttachmentCapsule from '@/components/AttachmentCapsule.vue'
import MailDate from '@/components/MailDate.vue'

import type { LayoutType, Thread } from '@/types'

const { mail, userLayout } = defineProps<{ mail: Thread; userLayout: LayoutType }>()

const emit = defineEmits(['select-thread', 'deselect-thread'])

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
</script>
