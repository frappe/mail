<template>
	<!-- One thread list row. A full-row transparent overlay opens the thread; the star
	     sits on top of it as its own tap target. The overlay is layered ABOVE the avatar/
	     content (so iOS hit-testing — which returns the top-most view, not the first with a
	     handler — routes those taps to it) but BELOW the star (so the star still wins in its
	     area). Tapping anywhere but the star navigates. Horizontal insets are margins on grid
	     children, not container padding, per the iOS spacing constraints. -->
	<GridLayout columns="auto, *, auto" class="border-outline-gray-1 border-b py-3">
		<!-- avatar: sender image, else monochrome initials -->
		<UserAvatar
			col="0"
			class="ml-3"
			:name="senderName"
			:image="thread.user_image"
			verticalAlignment="top"
		/>

		<!-- content -->
		<StackLayout col="1" class="ml-3" verticalAlignment="top">
			<!-- line 1: unread dot + sender + draft badge. Flexbox so the name shrinks
			     (truncating) and the badge sits right after it, not right-aligned. -->
			<FlexboxLayout flexDirection="row" alignItems="center">
				<StackLayout
					v-if="!thread.seen"
					class="mr-1.5 h-2 w-2 rounded-full bg-blue-500"
					flexShrink="0"
				/>
				<Label
					:text="header"
					class="text-ink-gray-9 mr-2 text-base"
					:class="thread.seen ? 'font-medium' : 'font-bold'"
					textWrap="false"
					flexShrink="1"
				/>
				<Label
					v-if="thread.draft"
					:text="__('Draft')"
					class="bg-surface-red-1 text-ink-red-3 rounded px-1.5 py-0.5 text-xs font-bold"
					flexShrink="0"
				/>
			</FlexboxLayout>

			<!-- line 2: subject -->
			<Label
				:text="subjectText"
				class="mt-0.5 text-sm"
				:class="[
					thread.seen ? 'text-ink-gray-7' : 'text-ink-gray-9 font-semibold',
					hasSubject ? '' : 'italic',
				]"
				textWrap="false"
			/>

			<!-- line 3: preview -->
			<Label
				:text="previewText"
				class="text-ink-gray-5 mt-0.5 text-sm"
				:class="hasPreview ? '' : 'italic'"
				textWrap="false"
			/>

			<!-- attachment chip -->
			<GridLayout
				v-if="firstAttachment"
				columns="auto, auto"
				class="border-outline-gray-2 mt-2 rounded-lg border px-2.5 py-1.5"
				horizontalAlignment="left"
			>
				<Image
					v-if="attachmentIcon"
					col="0"
					:src="attachmentIcon"
					stretch="aspectFit"
					class="h-4 w-4"
					verticalAlignment="center"
				/>
				<Label
					v-else
					col="0"
					:text="lucide('file')"
					class="font-lucide text-ink-gray-5 text-base"
					verticalAlignment="center"
				/>
				<Label
					col="1"
					:text="attachmentName"
					class="text-ink-gray-6 ml-2 text-sm"
					textWrap="false"
					verticalAlignment="center"
				/>
			</GridLayout>
		</StackLayout>

		<!-- trailing column: timestamp pinned top, star pinned bottom. Both live in
		     the same cell with top/bottom alignment so they use the full row height. -->
		<Label
			col="2"
			:text="time"
			class="text-ink-gray-5 ml-2 mr-3 text-sm"
			horizontalAlignment="right"
			verticalAlignment="top"
		/>

		<!-- full-row tap target: open the thread (transparent, above content, below star) -->
		<GridLayout col="0" colSpan="3" @tap="$emit('open')" />

		<GridLayout
			col="2"
			class="mr-1 h-7 w-9"
			verticalAlignment="bottom"
			horizontalAlignment="right"
			@tap="$emit('star')"
		>
			<Label
				:text="lucide('star')"
				class="font-lucide text-xl"
				:class="thread.flagged ? 'text-ink-amber-2' : 'text-ink-gray-4'"
				horizontalAlignment="center"
				verticalAlignment="bottom"
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

// Collapse runs of whitespace/newlines to single spaces and trim — some mails
// have whitespace-only or multi-line subjects/previews, which iOS renders as
// odd blank lines (Android collapses them). Whitespace-only falls back below.
const clean = (s?: string | null) => (s ?? '').replace(/\s+/g, ' ').trim()

const hasSubject = computed(() => clean(props.thread.subject).length > 0)
const hasPreview = computed(() => clean(props.thread.preview).length > 0)
const subjectText = computed(() =>
	hasSubject.value ? clean(props.thread.subject) : __('[No subject]'),
)
const previewText = computed(() =>
	hasPreview.value ? clean(props.thread.preview) : __('— No message body —'),
)

const firstAttachment = computed(() =>
	props.thread.attachments?.find((a) => a.filename && a.disposition === 'attachment'),
)

// Colored file-type badge (bundled PNGs of the web's AttachmentCapsule icons)
// for media types; other types fall back to the lucide file glyph.
function attachmentImage(type?: string): string {
	if (!type) return ''
	if (type.startsWith('image/')) return '~/images/file-icons/image.png'
	if (type === 'application/pdf') return '~/images/file-icons/pdf.png'
	if (type.startsWith('video/')) return '~/images/file-icons/video.png'
	if (type.startsWith('audio/')) return '~/images/file-icons/audio.png'
	return ''
}

const attachmentIcon = computed(() => attachmentImage(firstAttachment.value?.type))

// Truncate long filenames (keeping the extension) so the chip can't overflow.
function truncateFilename(name: string, max = 28): string {
	if (name.length <= max) return name
	const dot = name.lastIndexOf('.')
	const ext = dot > 0 ? name.slice(dot) : ''
	const keep = Math.max(1, max - ext.length - 1)
	return `${name.slice(0, keep)}…${ext}`
}

const attachmentName = computed(() => truncateFilename(firstAttachment.value?.filename ?? ''))
</script>
