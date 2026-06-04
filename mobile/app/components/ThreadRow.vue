<template>
	<!-- One thread list row. Tap opens the thread; the star is its own tap target
	     (NativeScript routes a tap to the front-most handler, so tapping the star
	     does not also trigger the row's open). Horizontal insets are margins on
	     grid children, not container padding, per the iOS spacing constraints. -->
	<GridLayout
		columns="auto, *, auto"
		class="border-outline-gray-1 border-b py-3"
		@tap="$emit('open')"
	>
		<!-- avatar: sender image, else monochrome initials -->
		<UserAvatar
			col="0"
			class="ml-3"
			:name="senderName"
			:image="thread.user_image"
			verticalAlignment="top"
		/>

		<!-- content -->
		<StackLayout col="1" class="ml-3" verticalAlignment="center">
			<!-- line 1: unread dot + sender + time -->
			<GridLayout columns="auto, *, auto">
				<StackLayout
					v-if="!thread.seen"
					col="0"
					class="mr-1.5 h-2 w-2 rounded-full bg-blue-500"
					verticalAlignment="center"
				/>
				<Label
					col="1"
					:text="header"
					class="text-ink-gray-9 mr-2 text-base"
					:class="thread.seen ? 'font-medium' : 'font-bold'"
					textWrap="false"
					verticalAlignment="center"
				/>
				<Label
					col="2"
					:text="time"
					class="text-ink-gray-5 text-sm"
					verticalAlignment="center"
				/>
			</GridLayout>

			<!-- line 2: subject -->
			<Label
				:text="subjectText"
				class="mt-0.5 text-sm"
				:class="[
					thread.seen ? 'text-ink-gray-7' : 'text-ink-gray-9 font-semibold',
					thread.subject ? '' : 'italic',
				]"
				textWrap="false"
			/>

			<!-- line 3: preview -->
			<Label
				:text="previewText"
				class="text-ink-gray-5 mt-0.5 text-sm"
				:class="thread.preview ? '' : 'italic'"
				textWrap="false"
			/>

			<!-- attachment chip -->
			<StackLayout
				v-if="firstAttachment"
				orientation="horizontal"
				class="border-outline-gray-2 mt-2 rounded-lg border px-2.5 py-1.5"
				horizontalAlignment="left"
			>
				<Label
					:text="lucide('paperclip')"
					class="font-lucide text-ink-gray-5 text-sm"
					verticalAlignment="center"
				/>
				<Label
					:text="firstAttachment.filename"
					class="text-ink-gray-6 ml-1.5 text-sm"
					textWrap="false"
					verticalAlignment="center"
				/>
			</StackLayout>
		</StackLayout>

		<!-- trailing: star toggle -->
		<GridLayout col="2" class="ml-1 mr-3 h-9 w-9" verticalAlignment="top" @tap="$emit('star')">
			<Label
				:text="lucide('star')"
				class="font-lucide text-xl"
				:class="thread.flagged ? 'text-ink-amber-2' : 'text-ink-gray-4'"
				horizontalAlignment="center"
				verticalAlignment="center"
			/>
		</GridLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { formatListDate, formatRecipients } from '@/utils/format'
import { lucide } from '@/utils/lucide'
import UserAvatar from '@/components/UserAvatar.vue'

import type { Thread } from '@mail/types'

const props = defineProps<{ thread: Thread; mailboxIds: Record<string, string> }>()
defineEmits<{ open: []; star: [] }>()

const senderName = computed(() => props.thread.from_name || props.thread.from_email || '?')

// Outgoing threads (in Sent/Drafts) show recipients instead of the sender —
// mirrors the web MailListItem header logic.
const outgoing = computed(() => {
	const ids = props.thread.mailboxes?.map((m) => m.mailbox_id) ?? []
	return ids.includes(props.mailboxIds.sent) || ids.includes(props.mailboxIds.drafts)
})

const header = computed(() =>
	outgoing.value
		? formatRecipients(props.thread.recipients)
		: props.thread.from_name || props.thread.from_email,
)

const time = computed(() => formatListDate(props.thread.received_at))
const subjectText = computed(() => props.thread.subject || __('[No subject]'))
const previewText = computed(() => props.thread.preview || __('— No message body —'))

const firstAttachment = computed(() =>
	props.thread.attachments?.find((a) => a.filename && a.disposition === 'attachment'),
)
</script>
