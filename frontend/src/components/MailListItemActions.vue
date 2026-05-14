<template>
	<template v-if="isHovered && !isMobile">
		<Tooltip v-for="action in actions" :key="action.label" :text="action.label">
			<button class="action-btn" @click.stop.prevent="action.onClick">
				<component :is="action.icon" class="icon text-ink-gray-5" />
			</button>
		</Tooltip>
	</template>
	<Tooltip :text="mail.flagged ? __('Unstar Mail') : __('Star Mail')">
		<button class="action-btn" @click.stop.prevent="emit('setFlagged', !mail.flagged)">
			<Star
				class="icon text-ink-gray-5"
				:class="{
					'fill-ink-amber-2 text-ink-amber-2 stroke-ink-amber-2': mail.flagged,
				}"
			/>
		</button>
	</Tooltip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Archive, Mail, MailOpen, Star, Trash2 } from 'lucide-vue-next'
import { Tooltip } from 'frappe-ui'

import { useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'

import type { Thread } from '@/types'

const { isHovered, mail } = defineProps<{ isHovered: boolean; mail: Thread }>()
const emit = defineEmits(['setSeen', 'archiveThread', 'trashThread', 'deleteThread', 'setFlagged'])

const { isMobile } = useScreenSize()
const { mailboxIds } = userStore()

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
			label: __('Archive Thread'),
			onClick: () => emit('archiveThread'),
			icon: Archive,
			condition: !mail.mailboxes.some((m) => m.mailbox_id === mailboxIds.archive),
		},
		{
			label: __('Move to Trash'),
			onClick: () => emit('trashThread'),
			icon: Trash2,
			condition: !mail.mailboxes.some((m) => m.mailbox_id === mailboxIds.trash),
		},
		{
			label: __('Delete Thread'),
			onClick: () => emit('deleteThread'),
			icon: Trash2,
			condition: mail.mailboxes.some((m) => m.mailbox_id === mailboxIds.trash),
		},
	].filter((action) => action.condition),
)
</script>

<style scoped>
.action-btn {
	@apply relative after:absolute after:-inset-4 after:content-[''] sm:after:-inset-1.5;
}

.action-btn:hover > * {
	color: var(--ink-gray-8) !important;
	stroke-width: 2 !important;
}
</style>
