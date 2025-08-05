<template>
	<!-- Header -->
	<header class="flex items-center justify-between border-b px-3 py-2.5 sm:px-5">
		<div class="flex items-center space-x-2">
			<Button v-if="isMobile" icon="menu" variant="ghost" @click="openSidebar" />
			<Breadcrumbs
				:items="[{ label: mailboxName, route: { name: 'Mailbox', params: { mailbox } } }]"
			>
				<template #suffix>
					<div class="text-ink-gray-5 ml-2 self-end text-xs">
						{{
							__('{0} {1}', [
								mailCount?.data || 0,
								mailCount?.data == 1 ? 'thread' : 'threads',
							])
						}}
					</div>
				</template>
			</Breadcrumbs>
		</div>
		<HeaderActions :mailbox @reload-mails="reloadMails" />
	</header>

	<div class="relative flex h-[calc(100dvh-3.05rem)]">
		<!-- Loading -->
		<div
			v-if="threads?.loading && limit === 50"
			class="flex w-full flex-col items-center justify-center"
		>
			<div class="text-ink-gray-5 flex items-center space-x-2">
				<LoaderCircle class="h-5 w-5 animate-spin" />
				<span>{{ __('Loading...') }}</span>
			</div>
		</div>

		<template v-else-if="threads?.data?.length || filter">
			<div
				ref="mailSidebar"
				class="sticky top-16 flex flex-col border-r"
				:class="!isMobile && userLayout === 'split' ? 'w-1/3' : 'w-full'"
			>
				<!-- Toolbar/Actions -->
				<div class="flex items-center justify-between border-b px-3.5 py-2.5 sm:px-5">
					<div class="text-base">
						<span v-if="selections.length">{{
							__('{0} {1} selected', [
								String(selections.length),
								selections.length === 1 ? 'item' : 'items',
							])
						}}</span>
						<span v-else>{{ title }}</span>
					</div>
					<div class="flex items-center space-x-1.5 sm:space-x-3">
						<Tooltip
							v-if="!isMobile && !selections.length"
							:text="__('Select Layout')"
						>
							<Dropdown :options="LAYOUT_OPTIONS">
								<Button variant="ghost">
									<template #icon>
										<component
											:is="userLayout === 'full' ? Rows4 : PanelLeft"
											class="text-ink-gray-7 h-4 w-4"
										/>
									</template>
								</Button>
							</Dropdown>
						</Tooltip>

						<Tooltip v-if="!selections.length" :text="__('Filter')">
							<Dropdown :options="FILTER_OPTIONS">
								<Button variant="ghost">
									<template #icon>
										<component
											:is="ListFilter"
											class="text-ink-gray-7 h-4 w-4"
										/>
									</template>
								</Button>
							</Dropdown>
						</Tooltip>

						<Tooltip
							v-for="action in selectActions"
							:key="action.label"
							:text="action.label"
						>
							<Button variant="ghost" @click="action.onClick">
								<template #icon>
									<component :is="action.icon" class="text-ink-gray-7 h-4 w-4" />
								</template>
							</Button>
						</Tooltip>

						<Tooltip
							v-if="!!selections.length && mailbox !== 'starred'"
							:text="__('Move To')"
						>
							<Dropdown :options="moveToOptions">
								<Button variant="ghost">
									<template #icon>
										<component
											:is="FolderInput"
											class="text-ink-gray-7 h-4 w-4"
										/>
									</template>
								</Button>
							</Dropdown>
						</Tooltip>

						<div class="flex items-center border-l pl-3.5 sm:pl-5">
							<Tooltip :text="__('Select All')">
								<Checkbox
									v-model="allSelected"
									@change="allSelectedManuallyToggled = true"
								/>
							</Tooltip>
						</div>
					</div>
				</div>

				<!-- Mail list -->
				<div
					v-if="threads?.data?.length"
					class="h-full overflow-y-auto overscroll-contain"
					@scroll="loadMoreEmails"
				>
					<div v-for="(group, key) in groupedThreads" :key="key">
						<div class="text-ink-gray-6 border-b p-3.5 text-xs font-semibold sm:px-5">
							{{ getFormattedDate(key).toUpperCase() }}
						</div>
						<MailListItem
							v-for="mail in group"
							ref="mailItems"
							:key="mail.thread_id"
							:mail
							:user-layout
							:class="{ 'bg-surface-gray-1': mail.thread_id == threadID }"
							@click="
								router.push({
									name: 'Mail',
									params: { mailbox, threadID: mail.thread_id },
								})
							"
							@select-thread="
								(isManuallySelected: boolean) =>
									selectThread(mail.thread_id, isManuallySelected)
							"
							@deselect-thread="
								(isManuallySelected: boolean) =>
									deselectThread(mail.thread_id, isManuallySelected)
							"
							@set-seen="
								(seen: boolean) =>
									setSeen.submit({ thread_ids: [mail.thread_id], seen })
							"
							@trash-thread="
								moveThreads.submit({
									thread_ids: [mail.thread_id],
									move_to_mailbox: 'trash',
								})
							"
							@delete-thread="deleteThreads.submit([mail.thread_id])"
						/>
					</div>
					<div v-if="threads.loading" class="flex items-center justify-center py-4">
						<div class="text-ink-gray-5 flex items-center space-x-2">
							<LoaderCircle class="h-4 w-4 animate-spin" />
							<span class="text-sm">{{ __('Loading more mails...') }}</span>
						</div>
					</div>
				</div>
				<div v-else class="flex h-full items-center justify-center">
					<p class="text-ink-gray-5">
						{{ __('No mails found for the selected filter.') }}
					</p>
				</div>
			</div>
			<div class="flex cursor-col-resize justify-center" @mousedown="startResizing">
				<div
					ref="resizer"
					class="group-hover:bg-surface-gray-5 h-full rounded-full transition-all duration-300 ease-in-out"
				/>
			</div>

			<!-- Mail thread -->
			<div
				class="bg-surface-white overflow-y-auto"
				:class="{
					'w-2/3': !isMobile && userLayout === 'split',
					'absolute bottom-0 left-0 right-0 top-0': !isMobile && userLayout === 'full',
					'fixed inset-0': isMobile,
					hidden: (isMobile || userLayout === 'full') && !threadID,
				}"
			>
				<MailThread
					:mailbox
					:thread-i-d
					@reload-mails="reloadMails"
					@set-seen="(seen: boolean) => setSeen.submit({ thread_ids: [threadID], seen })"
					@move-thread="
						(move_to_mailbox: string) =>
							moveThreads.submit({ thread_ids: [threadID], move_to_mailbox })
					"
					@delete-thread="deleteThreads.submit([threadID])"
				/>
			</div>
		</template>

		<!-- No mails -->
		<div v-else class="text-ink-gray-5 flex w-full flex-col items-center justify-center">
			<NoMails class="text-ink-gray-2 mb-2 h-16 w-16" />
			<p>{{ __('You have no mails in this folder.') }}</p>
		</div>
	</div>
</template>
<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDebounceFn } from '@vueuse/core'
import {
	FolderInput,
	ListFilter,
	LoaderCircle,
	Mail,
	MailOpen,
	Mails,
	PanelLeft,
	Paperclip,
	RefreshCw,
	Rows4,
	Star,
	Trash2,
} from 'lucide-vue-next'
import { Breadcrumbs, Button, Checkbox, Dropdown, Tooltip, createResource } from 'frappe-ui'

import { getFormattedDate, startResizing } from '@/utils'
import { useScreenSize, useSidebar } from '@/utils/composables'
import { userStore } from '@/stores/user'
import HeaderActions from '@/components/HeaderActions.vue'
import NoMails from '@/components/Icons/NoMails.vue'
import MailListItem from '@/components/MailListItem.vue'
import MailThread from '@/components/MailThread.vue'

import type { LayoutType, Thread, UserResource } from '@/types'

const { mailbox, threadID } = defineProps<{ mailbox: string; threadID?: string }>()

const router = useRouter()
const { isMobile } = useScreenSize()
const { openSidebar } = useSidebar()

const socket = inject('$socket')
const user = inject('$user') as UserResource
const dayjs = inject('$dayjs')

const { mailboxes } = userStore()

// Selection

const mailItems = useTemplateRef('mailItems')

const selections = ref<string[]>([])
const allSelectedManuallyToggled = ref(false)
const allSelected = ref(false)

const lastSelected = ref<string>()
const isShiftPressed = ref(false)

const resetSelections = () => {
	allSelectedManuallyToggled.value = false
	allSelected.value = false
	mailItems.value?.forEach((item) => item?.setIsSelected(false))
	selections.value = []
}

const selectThread = (thread: string, isManuallySelected: boolean) => {
	if (selections.value.includes(thread)) return
	if (isShiftPressed.value) {
		const shiftSelectedIDs = getShiftSelectedIDs(thread)
		mailItems.value?.forEach((item) => {
			if (shiftSelectedIDs.includes(item?.id)) item?.setIsSelected(true)
		})
		selections.value = Array.from(new Set([...selections.value, ...shiftSelectedIDs]))
	} else selections.value.push(thread)
	if (isManuallySelected) lastSelected.value = thread
}

const deselectThread = (thread: string, isManuallySelected: boolean) => {
	if (isShiftPressed.value) {
		const shiftSelectedIDs = getShiftSelectedIDs(thread)
		mailItems.value?.forEach((item) => {
			if (shiftSelectedIDs.includes(item?.id)) item?.setIsSelected(false)
		})
		selections.value = selections.value.filter((m) => !shiftSelectedIDs.includes(m))
	} else selections.value = selections.value.filter((m) => m !== thread)
	if (isManuallySelected) lastSelected.value = thread
}

const getShiftSelectedIDs = (thread: string) => {
	const startIndex = threadIDs.value.indexOf(lastSelected.value)
	const endIndex = threadIDs.value.indexOf(thread)
	const lower = Math.min(startIndex, endIndex)
	const higher = Math.max(startIndex, endIndex)
	return threadIDs.value.slice(lower, higher + 1)
}

watch(
	() => selections.value.length,
	(val) => {
		allSelectedManuallyToggled.value = false
		allSelected.value = val === threads.data.length
	},
)

watch(allSelected, (val) => {
	if (allSelectedManuallyToggled.value)
		mailItems.value?.forEach((item) => item?.setIsSelected(val))
})

const handleKeyDown = (e: KeyboardEvent) => {
	if (e.key === 'Shift') isShiftPressed.value = true
}
const handleKeyUp = (e: KeyboardEvent) => {
	if (e.key === 'Shift') isShiftPressed.value = false
}

interface SelectAction {
	label: string
	onClick: () => void
	icon: typeof RefreshCw
	condition: boolean
}

const selectActions = computed((): SelectAction[] =>
	[
		{
			label: __('Move to Trash'),
			onClick: () =>
				moveThreads.submit({
					thread_ids: selections.value,
					mailbox,
					move_to_mailbox: 'trash',
				}),
			icon: Trash2,
			condition: !!selections.value.length && mailbox !== 'trash',
		},
		{
			label: __('Delete Threads'),
			onClick: () => deleteThreads.submit(selections.value),
			icon: Trash2,
			condition: !!selections.value.length && mailbox === 'trash',
		},
		{
			label: __('Mark as Read'),
			onClick: () => setSeen.submit({ thread_ids: selections.value, seen: true }),
			icon: MailOpen,
			condition: !!selections.value.length,
		},
		{
			label: __('Mark as Unread'),
			onClick: () => setSeen.submit({ thread_ids: selections.value, seen: false }),
			icon: Mail,
			condition: !!selections.value.length,
		},
		{
			label: __('Refresh'),
			onClick: () => fetchChanges.submit(),
			icon: RefreshCw,
			condition: !selections.value.length,
		},
	].filter((action) => action.condition),
)

// Main data

const limit = ref(50)
const filter = ref<string | null>(
	localStorage.getItem(`user:${user.data.name}:filter:${mailbox}`) || null,
)

const threads = createResource({
	url: 'mail.api.mail.get_mails_from_mailbox',
	makeParams: () => ({ mailbox, limit: limit.value, filter_by: filter.value }),
})

const threadIDs = computed(() => threads.data?.map((thread: Thread) => thread.thread_id) || [])

const groupedThreads = computed(() =>
	threads?.data?.reduce((groups, thread: Thread) => {
		const date = dayjs(thread.received_at).format('YYYY-MM-DD')
		if (!groups[date]) groups[date] = []

		groups[date].push(thread)
		return groups
	}, {}),
)

const mailCount = createResource({
	url: 'mail.api.mail.get_mailbox_thread_count',
	makeParams: () => ({ mailbox }),
	cache: [`${mailbox}MailCount`, user.data?.name],
})

const reloadMails = () => {
	threads.reload()
	mailCount.reload()
	mailboxes.reload()
	resetSelections()
}

watch(
	() => mailbox,
	() => {
		filter.value = localStorage.getItem(`user:${user.data.name}:filter:${mailbox}`) || null
		limit.value = 50
		reloadMails()
	},
	{ immediate: true },
)

onMounted(() => {
	window.addEventListener('keydown', handleKeyDown)
	window.addEventListener('keyup', handleKeyUp)

	socket.on('mail_created_or_updated', (updatedMailbox: string) => {
		if (updatedMailbox === mailbox) reloadMails()
		else if (['inbox', 'junk'].includes(updatedMailbox)) mailboxes.reload()
	})
})

onUnmounted(() => {
	window.removeEventListener('keydown', handleKeyDown)
	window.removeEventListener('keyup', handleKeyUp)
})

const loadMoreEmails = useDebounceFn((e) => {
	const { scrollTop, scrollHeight, clientHeight } = e.target
	if (scrollTop + clientHeight >= scrollHeight - 10 && threads?.data?.length === limit.value) {
		limit.value += 50
		threads.reload()
		setTimeout(
			() => e.target.scrollTo({ top: e.target.scrollHeight, behavior: 'smooth' }),
			100,
		)
	}
}, 500)

// Actions

interface SetSeenParams {
	thread_ids: string[]
	seen: boolean
}

const setSeen = createResource({
	url: 'mail.api.mail.set_seen',
	makeParams: (values: SetSeenParams) => ({ ...values, mailbox }),
	onSuccess: ({ thread_ids, seen }: SetSeenParams) => {
		mailboxes.reload()
		threads.data
			.filter((thread: Thread) => thread_ids.includes(thread.thread_id))
			.forEach((thread: Thread) => (thread.seen = seen ? 1 : 0))
		if (
			!seen &&
			threadID &&
			(thread_ids.includes(threadID) ||
				!threads.data.some((m: Thread) => thread_ids.includes(m.thread_id)))
		)
			router.push({ name: 'Mailbox', params: { mailbox } })
	},
})

const moveThreads = createResource({
	url: 'mail.api.mail.set_threads_mailbox',
	makeParams: ({
		thread_ids,
		move_to_mailbox,
	}: {
		thread_ids: string[]
		move_to_mailbox: string
	}) => ({
		thread_ids,
		mailbox,
		move_to_mailbox,
	}),
	onSuccess: reloadMails,
})

const moveToOptions = computed(() =>
	user.data.mailboxes
		.filter((m) => ![mailbox, 'sent', 'drafts'].includes(m.role))
		.map((m) => ({
			label: m.name,
			onClick: () =>
				moveThreads.submit({ thread_ids: selections.value, move_to_mailbox: m.role }),
		})),
)

const deleteThreads = createResource({
	url: 'mail.api.mail.delete_threads',
	makeParams: (thread_ids: string[]) => ({ thread_ids, mailbox }),
	onSuccess: reloadMails,
})

const fetchChanges = createResource({
	url: 'mail.api.mail.fetch_changes',
	onSuccess: reloadMails,
	onError: reloadMails,
})

// Filter

const FILTER_OPTIONS = [
	{
		label: __('All'),
		icon: Mails,
		onClick: () => setFilter(null),
	},
	{
		label: __('Unread'),
		icon: Mail,
		onClick: () => setFilter('unread'),
	},
	{
		label: __('Starred'),
		icon: Star,
		onClick: () => setFilter('starred'),
		condition: () => !['trash', 'starred'].includes(mailbox),
	},
	{
		label: __('Has attachments'),
		icon: Paperclip,
		onClick: () => setFilter('has_attachments'),
	},
]

const setFilter = (value: string | null) => {
	filter.value = value
	localStorage.setItem(`user:${user.data.name}:filter:${mailbox}`, value ?? '')
	threads.reload()
	resetSelections()
}

// Layout

const userLayout = ref<LayoutType>(
	(localStorage.getItem(`user:${user.data.name}:layout`) as LayoutType) || 'split',
)

const setUserLayout = (type: LayoutType) => {
	userLayout.value = type
	localStorage.setItem(`user:${user.data.name}:layout`, type)
}

const LAYOUT_OPTIONS = [
	{
		label: __('Full Width'),
		icon: Rows4,
		onClick: () => setUserLayout('full'),
	},
	{
		label: __('Vertical Split'),
		icon: PanelLeft,
		onClick: () => setUserLayout('split'),
	},
]

// UI formatting

const mailboxName = computed(() =>
	mailbox === 'starred'
		? __('Starred')
		: user.data.mailboxes.find((m) => m.role === mailbox)?.name,
)

const title = computed(() => {
	switch (filter.value) {
		case 'unread':
			return __('Unread Mails')
		case 'starred':
			return __('Starred Mails')
		case 'has_attachments':
			return __('Mails With Attachments')
		default:
			return __('All Mails')
	}
})
</script>
