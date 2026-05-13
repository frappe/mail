<template>
	<template v-if="isHovered">
		<Tooltip v-for="action in actions" :key="action.label" :text="action.label">
			<button
				class="text-ink-gray-5 hover:!text-ink-gray-8"
				@click.stop.prevent="action.onClick"
			>
				<component :is="action.icon" class="stroke-1.5 h-4 w-4" />
			</button>
		</Tooltip>
	</template>
	<Tooltip :text="mail.flagged ? __('Unstar Thread') : __('Star Thread')">
		<button
			class="text-ink-gray-5 hover:!text-ink-gray-8"
			@click.stop.prevent="emit('setFlagged', !mail.flagged)"
		>
			<Star
				class="stroke-1.5 h-4 w-4"
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

import { userStore } from '@/stores/user'

import type { Thread } from '@/types'

const { isHovered, mail } = defineProps<{ isHovered: boolean; mail: Thread }>()
const emit = defineEmits(['setSeen', 'archiveThread', 'trashThread', 'deleteThread', 'setFlagged'])

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
