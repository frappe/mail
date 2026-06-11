<template>
	<div class="bg-surface-white sticky top-0 flex items-center border-b p-2.5 sm:px-5">
		<Button
			variant="ghost"
			class="mr-2 shrink-0"
			@click="$router.push({ name: 'Mailbox', params: { mailbox }, query: route.query })"
		>
			<template #icon>
				<ChevronLeft class="text-ink-gray-7 h-4 w-4" />
			</template>
		</Button>
		<span
			v-if="thread.loading"
			class="bg-surface-gray-3 h-3.5 animate-pulse"
			:style="{
				width: `${Math.max(100, Math.random() * (isMobile ? 300 : 800))}px`,
			}"
		/>
		<template v-else>
			<Tooltip v-if="!isMobile" :text="thread?.data?.[0]?.subject">
				<h2 class="mr-2 select-none truncate font-semibold leading-5">
					{{ thread?.data?.[0]?.subject || __('[No subject]') }}
				</h2>
			</Tooltip>
			<div class="ml-auto shrink-0 space-x-2">
				<Dropdown v-if="user.data?.show_reading_pane" :options="threadActions">
					<Button variant="ghost" :tooltip="__('Actions')">
						<template #icon>
							<Ellipsis class="text-ink-gray-7 icon" />
						</template>
					</Button>
				</Dropdown>
				<template v-else>
					<Button
						v-for="action in threadActions.filter((a) => a.condition())"
						:key="action.label"
						:tooltip="action.label"
						variant="ghost"
						@click="action.onClick"
					>
						<template #icon>
							<component :is="action.icon" class="text-ink-gray-7 icon" />
						</template>
					</Button>
				</template>

				<Dropdown v-if="showAddTo" :options="addToOptions">
					<Button variant="ghost" :tooltip="__('Add To')">
						<template #icon>
							<FolderPlus class="text-ink-gray-7 icon" />
						</template>
					</Button>
				</Dropdown>
				<Dropdown v-if="threadMailboxes.length > 1" :options="removeFromOptions">
					<Button variant="ghost" :tooltip="__('Remove From')">
						<template #icon>
							<FolderMinus class="text-ink-gray-7 icon" />
						</template>
					</Button>
				</Dropdown>
				<Dropdown :options="moveToOptions">
					<Button variant="ghost" :tooltip="__('Move To')">
						<template #icon>
							<FolderInput class="text-ink-gray-7 icon" />
						</template>
					</Button>
				</Dropdown>

				<template v-if="threads.includes(threadID)">
					<Button
						variant="ghost"
						:tooltip="__('Previous Thread (↑/K)')"
						:disabled="threadID === threads[0]"
						@click="emit('prevThread')"
					>
						<template #icon>
							<ArrowLeft class="text-ink-gray-7 icon" />
						</template>
					</Button>

					<Button
						variant="ghost"
						:tooltip="__('Next Thread (↓/J)')"
						:disabled="threadID === threads.at(-1)"
						@click="emit('nextThread')"
					>
						<template #icon>
							<ArrowRight class="text-ink-gray-7 icon" />
						</template>
					</Button>
				</template>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { type Component, computed, h, inject } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from 'frappe-ui/icons'
import {
	Archive,
	ArrowLeft,
	ArrowRight,
	ChevronLeft,
	CircleAlert,
	CircleCheck,
	Ellipsis,
	FolderInput,
	FolderMinus,
	FolderPlus,
	Mail as MailIcon,
	Star,
	Trash2,
} from 'lucide-vue-next'
import { Button, Dropdown, Tooltip } from 'frappe-ui'
import type { createResource } from 'frappe-ui'

import { FOLDER_ICON_COLOR_MAP } from '@/constants'
import { getIcon } from '@/utils'
import { useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'

import type { Mail, MailboxData } from '@/types'

const { thread, threads } = defineProps<{ thread: typeof createResource; threads: string[] }>()
const emit = defineEmits([
	'setFlagged',
	'setSeen',
	'moveThread',
	'addThreadToMailbox',
	'removeThreadFromMailbox',
	'setSpamStatus',
	'deleteThread',
	'prevThread',
	'nextThread',
])

const { isMobile } = useScreenSize()
const route = useRoute()
const { mailboxes, mailboxIds } = userStore()

const user = inject('$user')

const mailbox = computed(() => route.params.mailbox as string)
const threadID = computed(() => route.params.threadID as string)

const threadMailboxes = computed(() => {
	if (!thread?.data?.length) return []
	return thread.data
		.filter((mail: Mail) => mail.id)
		.map((mail: Mail) => mail.mailboxes.map((m) => m.mailbox_id))
		.reduce((common, ids: string[]) => common.filter((id) => ids.includes(id)))
})

const threadActions = computed((): Action[] => [
	{
		label: __('Star Thread'),
		onClick: () =>
			emit(
				'setFlagged',
				thread.data.map((m) => m.id),
				true,
			),
		icon: Star,
		condition: () => thread.data.some((m) => !m.flagged),
	},
	{
		label: __('Unstar Thread'),
		onClick: () =>
			emit(
				'setFlagged',
				thread.data.map((m) => m.id),
				false,
			),
		icon: h(Star, { class: 'fill-ink-amber-2 text-ink-amber-2 stroke-ink-amber-2' }),
		condition: () => thread.data.every((m) => m.flagged),
	},
	{
		label: __('Mark as Unread (U)'),
		onClick: () => emit('setSeen', false),
		icon: MailIcon,
		condition: () => true,
	},
	{
		label: __('Archive Thread (E)'),
		onClick: () =>
			emit(
				mailbox.value === mailboxIds.sent ? 'addThreadToMailbox' : 'moveThread',
				mailboxIds.archive,
			),
		icon: Archive,
		condition: () => !threadMailboxes.value.includes(mailboxIds.archive),
	},
	{
		label: __('Mark as Junk (!)'),
		onClick: () => emit('setSpamStatus', true),
		icon: CircleAlert,
		condition: () =>
			!threadMailboxes.value.some((m: string) =>
				[mailboxIds.junk, mailboxIds.drafts].includes(m),
			),
	},
	{
		label: __('Mark as Not Junk'),
		onClick: () => emit('setSpamStatus', false),
		icon: CircleCheck,
		condition: () => threadMailboxes.value.includes(mailboxIds.junk),
	},
	{
		label: __('Move to Trash (Delete)'),
		onClick: () => emit('moveThread', mailboxIds.trash),
		icon: Trash2,
		condition: () => !threadMailboxes.value.includes(mailboxIds.trash),
	},
	{
		label: __('Delete Thread (Shift+Delete)'),
		onClick: () => emit('deleteThread'),
		icon: Trash2,
		condition: () => threadMailboxes.value.includes(mailboxIds.trash),
	},
])

const showAddTo = computed(() =>
	threadMailboxes.value.every((m) => ![mailboxIds.junk, mailboxIds.trash].includes(m)),
)

const addToOptions = computed(() =>
	mailboxes.data
		?.filter(
			(m) =>
				(!m.role || ['inbox', 'archive'].includes(m.role)) &&
				!threadMailboxes.value.includes(m.id),
		)
		.map((m) => getMailboxOption(m, 'addThreadToMailbox')),
)

const removeFromOptions = computed(() =>
	mailboxes.data
		?.filter((m) => threadMailboxes.value.includes(m.id))
		.map((m) => getMailboxOption(m, 'removeThreadFromMailbox')),
)

const moveToOptions = computed(() => {
	const excludedMailboxes = new Set([
		mailboxIds.sent,
		mailboxIds.drafts,
		...threadMailboxes.value,
	])
	return mailboxes.data
		?.filter((m) => !excludedMailboxes.has(m.id))
		.map((m) => getMailboxOption(m, 'moveThread'))
})

const getMailboxOption = (
	mailbox: MailboxData,
	emitName: 'moveThread' | 'addThreadToMailbox' | 'removeThreadFromMailbox',
) => ({
	label: mailbox._name,
	icon: h(Icon, { name: getIcon(mailbox), class: FOLDER_ICON_COLOR_MAP[mailbox.color!] }),
	onClick: () => emit(emitName, mailbox.id),
})

interface Action {
	label: string
	onClick: () => void
	icon: typeof ArrowLeft | Component
	condition: () => boolean
}
</script>
