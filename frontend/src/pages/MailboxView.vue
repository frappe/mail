<template>
	<!-- Header -->
	<header class="flex items-center justify-between border-b px-3 py-2.5 sm:px-5">
		<div class="flex items-center space-x-2">
			<Button v-if="isMobile" icon="menu" variant="ghost" @click="openSidebar" />
			<Breadcrumbs
				:items="[{ label: mailboxName, route: { name: 'Mailbox', params: { mailbox } } }]"
			>
				<template v-if="mailbox !== 'starred'" #suffix>
					<span class="text-ink-gray-5 ml-2 self-end pb-px text-xs">
						{{ noOfThreads }}
					</span>
				</template>
			</Breadcrumbs>
		</div>
		<HeaderActions @reload-mails="reloadMails(true, ['drafts', 'sent'])" />
	</header>
	<div
		v-if="
			[mailboxIds.trash, mailboxIds.junk].includes(mailbox) &&
			threads.data?.length &&
			(showReadingPane || !threadID)
		"
		class="space-x-1 border-b px-3 py-2.5 sm:px-5"
	>
		<span class="text-ink-gray-5">
			{{ __('Items in this mailbox will be automatically deleted after 30 days.') }}
		</span>
		<Button :label="__('Delete Now')" variant="ghost" @click="showEmptyMailbox = true" />
	</div>

	<div
		class="relative flex"
		:class="
			[mailboxIds.trash, mailboxIds.junk].includes(mailbox)
				? 'h-[calc(100dvh-6.1rem)]'
				: 'h-[calc(100dvh-3.05rem)]'
		"
	>
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
				:class="!isMobile && showReadingPane ? 'w-1/3' : 'w-full'"
			>
				<!-- Toolbar/Actions -->
				<div class="flex items-center border-b px-3.5 py-2.5 sm:px-5">
					<div class="sm:mr-5.5 ml-3 mr-3.5">
						<Tooltip :text="__('Select All')">
							<Checkbox
								:model-value="isAllSelected"
								size="md"
								@update:model-value="toggleSelectAll"
							/>
						</Tooltip>
					</div>
					<div class="mr-auto text-base">
						<span v-if="selections.length">
							{{
								selections.length === 1
									? __('1 item selected')
									: __('{0} items selected', [String(selections.length)])
							}}
						</span>
						<span v-else>{{ title }}</span>
					</div>
					<div class="flex items-center space-x-1.5 sm:space-x-3">
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
					</div>
				</div>

				<!-- Mail list -->
				<div
					v-if="threads?.data?.length"
					ref="mailList"
					class="h-full overflow-y-auto overscroll-contain"
					@click="mailListClicked = true"
					@scroll="loadMoreEmails"
				>
					<div v-for="(group, key) in groupedThreads" :key="key">
						<Tooltip
							:text="
								isLastGroup(key)
									? ''
									: __(collapsedGroups.includes(key) ? 'Expand' : 'Collapse')
							"
						>
							<div
								class="text-ink-gray-6 group flex items-center border-b p-3.5 text-xs font-semibold sm:px-5"
								:class="{ 'cursor-pointer': !isLastGroup(key) }"
								@click="toggleGroupCollapse(key)"
							>
								<Checkbox
									:model-value="isGroupSelected(key)"
									size="md"
									class="ml-1.5 mr-[11px]"
									@update:model-value="
										toggleSelect(getGroupThreads(key), $event)
									"
									@click.stop
								/>
								<span class="select-none">
									{{ getFormattedDate(key).toUpperCase() }}
								</span>

								<component
									:is="
										collapsedGroups.includes(key) ? ChevronRight : ChevronDown
									"
									v-if="!isLastGroup(key)"
									class="text-ink-gray-5 ml-auto h-4 w-4"
								/>
							</div>
						</Tooltip>
						<template v-if="!collapsedGroups.includes(key)">
							<MailListItem
								v-for="mail in group"
								ref="mailItems"
								:key="mail.thread_id"
								:mail
								:is-selected="selections.includes(mail.thread_id)"
								:class="{ '!bg-surface-blue-1': mail.thread_id == threadID }"
								@click="
									router.push({
										name: 'Mail',
										params: { mailbox, threadID: mail.thread_id },
									})
								"
								@set-seen="
									(seen: boolean) =>
										setSeen.submit({ thread_ids: [mail.thread_id], seen })
								"
								@trash-thread="
									moveThreads.submit({
										thread_ids: [mail.thread_id],
										move_to_mailbox: mailboxIds.trash,
									})
								"
								@delete-thread="deleteThreads.submit([mail.thread_id])"
								@set-selected="
									(selected: boolean) => toggleSelect([mail.thread_id], selected)
								"
							/>
						</template>
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
					'w-2/3': !isMobile && showReadingPane,
					'absolute bottom-0 left-0 right-0 top-0': !isMobile && !showReadingPane,
					'fixed inset-0': isMobile,
					hidden: (isMobile || !showReadingPane) && !threadID,
				}"
			>
				<MailThread
					:mailbox
					:thread-i-d
					:threads="threadIDs"
					@reload-mails="reloadMails"
					@set-seen="(seen: boolean) => setSeen.submit({ thread_ids: [threadID], seen })"
					@move-thread="
						(move_to_mailbox: string) =>
							moveThreads.submit({ thread_ids: [threadID], move_to_mailbox })
					"
					@set-spam-status="
						(spam: boolean) =>
							setThreadsSpamStatus.submit({ thread_ids: [threadID], spam })
					"
					@delete-thread="deleteThreads.submit([threadID])"
					@prev-thread="goToThreadByOffset(-1)"
					@next-thread="goToThreadByOffset(1)"
				/>
			</div>
		</template>

		<!-- No mails -->
		<div v-else class="text-ink-gray-5 flex w-full flex-col items-center justify-center">
			<NoMails class="text-ink-gray-2 mb-2 h-16 w-16" />
			<p>{{ __('You have no mails in this folder.') }}</p>
		</div>
	</div>

	<Dialog v-model="showEmptyMailbox" :options="emptyMailboxOptions" />
</template>
<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { onClickOutside, useDebounceFn } from '@vueuse/core'
import {
	BadgeAlert,
	BadgeCheck,
	ChevronDown,
	ChevronRight,
	FolderInput,
	ListFilter,
	LoaderCircle,
	Mail,
	MailOpen,
	Mails,
	Paperclip,
	RefreshCw,
	Star,
	Trash2,
} from 'lucide-vue-next'
import {
	Breadcrumbs,
	Button,
	Checkbox,
	Dialog,
	Dropdown,
	Tooltip,
	createResource,
} from 'frappe-ui'

import { getFormattedDate, raiseToast, startResizing } from '@/utils'
import { useLayout, useScreenSize, useSidebar } from '@/utils/composables'
import { type MailboxRole, userStore } from '@/stores/user'
import HeaderActions from '@/components/HeaderActions.vue'
import NoMails from '@/components/Icons/NoMails.vue'
import MailListItem from '@/components/MailListItem.vue'
import MailThread from '@/components/MailThread.vue'

import type { Thread, UserResource } from '@/types'

const { mailbox, threadID } = defineProps<{ mailbox: string; threadID?: string }>()

const router = useRouter()
const { isMobile } = useScreenSize()
const { openSidebar } = useSidebar()
const { showReadingPane, groupMessagesBy } = useLayout()

const socket = inject('$socket')
const user = inject('$user') as UserResource
const dayjs = inject('$dayjs')

const { mailboxes, mailboxIds } = userStore()

// Thread Groups

const groupedThreads = computed<Record<string, Thread[]>>(() =>
	threads?.data?.reduce((groups: Record<string, Thread[]>, thread: Thread) => {
		const date = dayjs(thread.received_at).format('YYYY-MM-DD')
		if (!groups[date]) groups[date] = []

		groups[date].push(thread)
		return groups
	}, {}),
)

const isLastGroup = (key: string) => Object.keys(groupedThreads.value).at(-1) === key

const collapsedGroups = ref<string[]>([])

const toggleGroupCollapse = (key: string) => {
	if (isLastGroup(key)) return

	if (collapsedGroups.value.includes(key))
		return (collapsedGroups.value = collapsedGroups.value.filter((d) => d !== key))

	collapsedGroups.value.push(key)
	if (groupedThreads.value[key]?.some((thread) => thread.thread_id === threadID))
		router.push({ name: 'Mailbox', params: { mailbox } })
	toggleSelect(getGroupThreads(key), false)
}

const getGroupThreads = (group: string) => groupedThreads.value[group]?.map((t) => t.thread_id)

watch(
	() => threadID,
	(val) => {
		if (!val) return

		for (const group of collapsedGroups.value) {
			if (getGroupThreads(group).includes(val))
				return (collapsedGroups.value = collapsedGroups.value.filter((d) => d !== group))
		}
	},
)

// Selection

const mailList = useTemplateRef('mailList')
const mailListClicked = ref(true)
onClickOutside(mailList, () => (mailListClicked.value = false))

const mailItems = useTemplateRef('mailItems')

const selections = ref<string[]>([])
const lastSelected = ref<string[]>()
const isShiftPressed = ref(false)

const isAllSelected = computed(
	() => threadIDs.value.length && selections.value.length === threadIDs.value.length,
)

watch(selections, (val) => {
	collapsedGroups.value = collapsedGroups.value.filter(
		(group) => !getGroupThreads(group).some((thread) => val.includes(thread)),
	)
})

const toggleSelect = (threadIDs: string[], selected: boolean) => {
	const allIDs = new Set([...threadIDs, ...getShiftSelectedIDs(threadIDs[0])])
	if (selected) selections.value = [...new Set([...selections.value, ...allIDs])]
	else selections.value = selections.value.filter((id) => !allIDs.has(id))
	lastSelected.value = threadIDs
}

const getShiftSelectedIDs = (thread: string) => {
	if (!(isShiftPressed.value && lastSelected.value?.length)) return []

	const currentIndex = threadIDs.value.indexOf(thread)
	const firstIndex = threadIDs.value.indexOf(lastSelected.value[0])
	const lastIndex = threadIDs.value.indexOf(lastSelected.value.at(-1))

	const farthestIndex =
		Math.abs(currentIndex - firstIndex) > Math.abs(currentIndex - lastIndex)
			? firstIndex
			: lastIndex

	const [lower, higher] = [farthestIndex, currentIndex].sort((a, b) => a - b)
	return threadIDs.value.slice(lower, higher + 1)
}

const toggleSelectAll = (selected: boolean) => {
	if (selected) selections.value = [...threadIDs.value]
	else selections.value = []
	lastSelected.value = undefined
}

const resetSelections = () => {
	selections.value = []
	lastSelected.value = undefined
}

const isGroupSelected = (key: string) =>
	getGroupThreads(key).every((id) => selections.value.includes(id))

const handleKeyDown = (e: KeyboardEvent) => {
	if (e.key === 'Shift') isShiftPressed.value = true

	if (
		showReadingPane.value &&
		mailListClicked.value &&
		threadID &&
		(e.key === 'ArrowUp' || e.key === 'ArrowDown')
	) {
		e.preventDefault()

		const offset = e.key === 'ArrowUp' ? -1 : 1
		goToThreadByOffset(offset)
		lastSelected.value = [threadID]

		const thread = getThreadByOffset(offset)
		if (thread && isShiftPressed.value) {
			if (selections.value.includes(thread)) toggleSelect([threadID, thread], false)
			else toggleSelect([threadID, thread], true)
		}
	}
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
			label: __('Mark as Junk'),
			onClick: () =>
				setThreadsSpamStatus.submit({ thread_ids: selections.value, mailbox, spam: true }),
			icon: BadgeAlert,
			condition:
				!!selections.value.length &&
				![mailboxIds.junk, mailboxIds.drafts].includes(mailbox),
		},
		{
			label: __('Mark as Not Junk'),
			onClick: () =>
				setThreadsSpamStatus.submit({
					thread_ids: selections.value,
					mailbox,
					spam: false,
				}),
			icon: BadgeCheck,
			condition: !!selections.value.length && mailbox === mailboxIds.junk,
		},
		{
			label: __('Move to Trash'),
			onClick: () =>
				moveThreads.submit({
					thread_ids: selections.value,
					mailbox,
					move_to_mailbox: mailboxIds.trash,
				}),
			icon: Trash2,
			condition: !!selections.value.length && mailbox !== mailboxIds.trash,
		},
		{
			label: __('Delete Threads'),
			onClick: () => deleteThreads.submit(selections.value),
			icon: Trash2,
			condition: !!selections.value.length && mailbox === mailboxIds.trash,
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
			onClick: () => reloadMails(),
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
	url: 'mail.api.mail.get_threads',
	makeParams: () => ({ mailbox, limit: limit.value, filter_by: filter.value }),
})

const threadIDs = computed(() => threads.data?.map((thread: Thread) => thread.thread_id) || [])

const reloadMails: (reloadMailboxes?: boolean, mailboxRoles?: MailboxRole[]) => void = (
	reloadMailboxes = true,
	mailboxRoles = [],
) => {
	if (mailboxRoles.length && !mailboxRoles.map((m) => mailboxIds[m]).includes(mailbox)) return

	resetSelections()
	threads.reload()
	if (reloadMailboxes) mailboxes.reload()
}

watch(
	() => mailbox,
	() => {
		filter.value = localStorage.getItem(`user:${user.data.name}:filter:${mailbox}`) || null
		limit.value = 50
		reloadMails(false)
	},
	{ immediate: true },
)

onMounted(() => {
	window.addEventListener('keydown', handleKeyDown)
	window.addEventListener('keyup', handleKeyUp)

	socket.on('new_mail_created', (updatedMailboxes: string[]) => {
		if (updatedMailboxes.includes(mailbox)) reloadMails()
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
	makeParams: ({ thread_ids, seen }: SetSeenParams) => ({ thread_ids, seen, mailbox }),
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

interface MoveThreadsParams {
	thread_ids: string[]
	move_to_mailbox: string
}

const moveThreads = createResource({
	url: 'mail.api.mail.set_threads_mailbox',
	makeParams: ({ thread_ids, move_to_mailbox }: MoveThreadsParams) => ({
		thread_ids,
		mailbox,
		move_to_mailbox,
	}),
	onSuccess: (thread_ids: string[]) => {
		if (threadID && thread_ids.includes(threadID))
			router.push({ name: 'Mailbox', params: { mailbox } })
		reloadMails()
	},
})

const moveToOptions = computed(() =>
	mailboxes.data
		?.filter((m) => ![mailbox, mailboxIds.sent, mailboxIds.drafts].includes(m.id))
		.map((m) => ({
			label: m._name,
			onClick: () =>
				moveThreads.submit({ thread_ids: selections.value, move_to_mailbox: m.id }),
		})),
)

interface SetThreadsSpamStatusParams {
	thread_ids: string[]
	spam: boolean
}

const setThreadsSpamStatus = createResource({
	url: 'mail.api.mail.set_threads_spam_status',
	makeParams: ({ thread_ids, spam }: SetThreadsSpamStatusParams) => ({
		thread_ids,
		mailbox,
		spam,
	}),
	onSuccess: (thread_ids: string[]) => {
		if (threadID && thread_ids.includes(threadID))
			router.push({ name: 'Mailbox', params: { mailbox } })
		reloadMails()
	},
})

const deleteThreads = createResource({
	url: 'mail.api.mail.delete_threads',
	makeParams: (thread_ids: string[]) => ({ thread_ids, mailbox }),
	onSuccess: (thread_ids: string[]) => {
		if (threadID && thread_ids.includes(threadID))
			router.push({ name: 'Mailbox', params: { mailbox } })
		reloadMails()
	},
})

const getThreadByOffset = (offset: number) =>
	threadIDs.value[threadIDs.value.indexOf(threadID) + offset]

const goToThreadByOffset = (offset: number) => {
	const targetThread = getThreadByOffset(offset)
	if (!targetThread) return

	router.push({ name: 'Mail', params: { mailbox, threadID: targetThread } })
	const el = mailItems.value?.find((el) => el?.id === targetThread)?.$el
	if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const showEmptyMailbox = ref(false)

const emptyMailbox = createResource({
	url: 'mail.api.mail.empty_user_mailbox',
	makeParams: () => ({ mailbox }),
	onSuccess: () => {
		raiseToast(__('{0} emptied successfully', [mailboxName.value]))
		reloadMails()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

const emptyMailboxOptions = computed(() => ({
	title: __('Empty {0}', [mailboxName.value]),
	message: __(`Are you sure you want to empty the contents of this mailbox?`),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			onClick: () => {
				emptyMailbox.submit()
				showEmptyMailbox.value = false
			},
		},
	],
}))

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
		condition: () => ![mailboxIds.trash, 'starred'].includes(mailbox),
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

// UI formatting

const mailboxObj = computed(() => mailboxes.data?.find((m) => m.id === mailbox))
const mailboxName = computed(() =>
	mailbox === 'starred' ? __('Starred') : mailboxObj.value?._name,
)
const noOfThreads = computed(
	() =>
		`${mailboxObj.value?.total_threads} ${mailboxObj.value?.total_threads == 1 ? __('thread') : __('threads')}`,
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
