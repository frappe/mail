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
		<HeaderActions @reload-mails="reloadThreads(true, ['drafts', 'sent'])" />
	</header>
	<div
		v-if="
			[mailboxIds.trash, mailboxIds.junk].includes(mailbox) &&
			!threadsResource.data?.loading &&
			threadsResource.data?.length &&
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
			v-if="
				(!threadsResource?.data?.length && threadsResource?.loading && limit === 50) ||
				emptyMailbox.loading
			"
			class="flex w-full flex-col items-center justify-center"
		>
			<div class="text-ink-gray-5 flex items-center space-x-2">
				<LoaderCircle class="h-5 w-5 animate-spin" />
				<span>{{ __('Loading...') }}</span>
			</div>
		</div>

		<template v-else-if="threadsResource?.data?.length || filter">
			<div
				ref="mailSidebar"
				class="sticky top-16 flex flex-col border-r"
				:class="!isMobile && showReadingPane ? 'w-1/3' : 'w-full'"
			>
				<!-- Toolbar/Actions -->
				<div class="flex items-center border-b px-3.5 py-2.5 sm:px-5">
					<div class="sm:mr-5.5 ml-3 mr-5">
						<Tooltip
							:text="
								isAllSelected
									? __('Clear All (Esc)')
									: __('Select All ({0}+A)', [modifier])
							"
						>
							<Checkbox
								:model-value="isAllSelected"
								size="md"
								@update:model-value="toggleSelectAll"
							/>
						</Tooltip>
					</div>
					<p class="mr-auto pb-[2px]">{{ title }}</p>
					<div class="flex items-center space-x-1.5 sm:space-x-3">
						<Dropdown
							v-if="!selections.length && mailbox !== 'search'"
							:options="FILTER_OPTIONS"
						>
							<Button variant="ghost" :tooltip="__('Filter')">
								<template #icon>
									<component :is="ListFilter" class="text-ink-gray-7 h-4 w-4" />
								</template>
							</Button>
						</Dropdown>

						<Button
							v-for="action in selectActions"
							:key="action.label"
							:tooltip="action.label"
							variant="ghost"
							@click="action.onClick"
						>
							<template #icon>
								<component :is="action.icon" class="text-ink-gray-7 h-4 w-4" />
							</template>
						</Button>

						<Dropdown
							v-if="!!selections.length && !['search', 'starred'].includes(mailbox)"
							:options="moveToOptions"
						>
							<Button variant="ghost" :tooltip="__('Move To')">
								<template #icon>
									<component :is="FolderInput" class="text-ink-gray-7 h-4 w-4" />
								</template>
							</Button>
						</Dropdown>
					</div>
				</div>

				<!-- Mail list -->
				<div
					v-if="threadsResource?.data?.length"
					class="h-full overflow-y-auto overscroll-contain"
					@scroll="loadMoreThreads"
				>
					<TransitionGroup name="mail-group" tag="div">
						<div v-for="(group, key) in groupedThreads" :key="key">
							<Tooltip
								v-if="groupMessagesBy !== 'none'"
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
									<span class="select-none pt-[2px]">
										{{
											getFormattedDate(
												key,
												groupMessagesBy === 'month',
											).toUpperCase()
										}}
									</span>

									<component
										:is="
											collapsedGroups.includes(key)
												? ChevronRight
												: ChevronDown
										"
										v-if="!isLastGroup(key)"
										class="text-ink-gray-5 ml-auto h-4 w-4"
									/>
								</div>
							</Tooltip>
							<TransitionGroup
								v-if="!collapsedGroups.includes(key)"
								name="mail-item"
								tag="div"
							>
								<MailListItem
									v-for="mail in group"
									ref="mailItems"
									:key="mail.name"
									:mailbox
									:mail
									:is-selected="selections.includes(mail.thread_id)"
									class="border-l-transparent transition-all sm:border-l"
									:class="{
										'!bg-surface-blue-1': mail.thread_id === threadID,
										'!border-l-blue-500': mail.thread_id === threadInFocus,
									}"
									@set-seen="
										(seen: boolean) =>
											handleSetSeen({ [Number(seen)]: [mail.thread_id] })
									"
									@trash-thread="
										handleMoveThreads({ [mailboxIds.trash]: [mail.thread_id] })
									"
									@delete-thread="junkOrDeleteThreads([mail.thread_id], false)"
									@set-selected="
										(selected: boolean) =>
											toggleSelect([mail.thread_id], selected)
									"
								/>
							</TransitionGroup>
						</div>
					</TransitionGroup>
					<div
						v-if="threadsResource.loading && threadsResource.data.length === limit"
						class="flex items-center justify-center py-4"
					>
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
					@reload-mails="reloadThreads"
					@set-seen="
						(seen: boolean) =>
							seen
								? setSeen.submit({ 1: [threadID!] })
								: handleSetSeen({ 0: [threadID!] })
					"
					@move-thread="
						(moveToMailbox: string) =>
							handleMoveThreads({ [moveToMailbox]: [threadID!] })
					"
					@set-spam-status="
						(spam: boolean) =>
							spam
								? junkOrDeleteThreads([threadID!], true)
								: handleSetSpamStatus({ 0: [threadID!] })
					"
					@delete-thread="junkOrDeleteThreads([threadID!], false)"
					@prev-thread="goToThreadByOffset(-1)"
					@next-thread="goToThreadByOffset(1)"
				/>
			</div>
		</template>

		<!-- No mails -->
		<div v-else class="text-ink-gray-5 flex w-full flex-col items-center justify-center">
			<NoMails class="text-ink-gray-2 mb-2 h-16 w-16" />
			<p>
				{{
					mailbox === 'search'
						? __('No results found for the given query.')
						: __('You have no mails in this folder.')
				}}
			</p>
		</div>
	</div>

	<Dialog v-model="showEmptyMailbox" :options="emptyMailboxOptions" />
	<Dialog v-model="showJunkOrDeleteThreads" :options="junkOrDeleteThreadsOptions" />
	<ShortcutsModal v-model="showShortcuts" />
</template>
<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDebounceFn } from '@vueuse/core'
import {
	ChevronDown,
	ChevronRight,
	CircleAlert,
	CircleCheck,
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
	toast,
} from 'frappe-ui'

import {
	getFormattedDate,
	isMac,
	raisePromiseToast,
	raiseToast,
	shouldIgnoreKeypress,
	startResizing,
} from '@/utils'
import { useLayout, useScreenSize, useSidebar, useUndo } from '@/utils/composables'
import { type MailboxRole, userStore } from '@/stores/user'
import HeaderActions from '@/components/HeaderActions.vue'
import NoMails from '@/components/Icons/NoMails.vue'
import MailListItem from '@/components/MailListItem.vue'
import MailThread from '@/components/MailThread.vue'
import ShortcutsModal from '@/components/Modals/ShortcutsModal.vue'

import type { Thread, UserResource } from '@/types'

const { mailbox, threadID } = defineProps<{ mailbox: string; threadID?: string }>()

const route = useRoute()
const router = useRouter()
const { isMobile } = useScreenSize()
const { openSidebar } = useSidebar()
const { showReadingPane, groupMessagesBy } = useLayout()
const { setUndoAction, undo } = useUndo()

const socket = inject('$socket')
const user = inject('$user') as UserResource
const dayjs = inject('$dayjs')

const { mailboxes, mailboxIds } = userStore()

// Thread Groups

const groupedThreads = computed<Record<string, Thread[]>>(() =>
	threadsResource.value?.data?.reduce((groups: Record<string, Thread[]>, thread: Thread) => {
		const date = dayjs(thread.received_at).format(
			groupMessagesBy.value === 'day' ? 'YYYY-MM-DD' : 'YYYY-MM',
		)
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
	if (groupedThreads.value[key]?.some((thread) => thread.thread_id === threadID)) goToMailbox()
	toggleSelect(getGroupThreads(key), false)
}

const getGroupThreads = (group: string) => groupedThreads.value[group]?.map((t) => t.thread_id)

watch(groupMessagesBy, () => (collapsedGroups.value = []))

const threadInFocus = ref<string>()

watch(
	() => threadID,
	(val) => {
		if (!val) return

		setTimeout(() => focusOnThread(val))
		for (const group of collapsedGroups.value) {
			if (getGroupThreads(group).includes(val))
				return (collapsedGroups.value = collapsedGroups.value.filter((d) => d !== group))
		}
	},
	{ immediate: true },
)

// Selection

const mailItems = useTemplateRef('mailItems')

const selections = ref<string[]>([])
const lastSelected = ref<string[]>()

const isAllSelected = computed(
	() => threadIDs.value.length && selections.value.length === threadIDs.value.length,
)

watch(selections, (val) => {
	collapsedGroups.value = collapsedGroups.value.filter(
		(group) => !getGroupThreads(group).some((thread) => val.includes(thread)),
	)
})

const toggleSelect = (
	threadIDs: string[],
	selected: boolean,
	isKeyboardSelect: boolean = false,
) => {
	const allIDs = new Set([
		...threadIDs,
		...(isKeyboardSelect ? [] : getShiftSelectedIDs(threadIDs[0])),
	])
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

// Shortcuts

const showShortcuts = ref(false)

const modifier = computed(() => (isMac ? '⌘' : 'Ctrl'))

const isShiftPressed = ref(false)
const isGPressed = ref(false)
const gPressTimeout = ref<ReturnType<typeof setTimeout>>()

const handleKeyDown = (e: KeyboardEvent) => {
	isShiftPressed.value = e.shiftKey
	const key = e.key.toLowerCase()

	// Handle Ctrl/Cmd+A (Select All)
	if ((e.metaKey || e.ctrlKey) && key === 'a' && !shouldIgnoreKeypress(e, true)) {
		e.preventDefault()
		isGPressed.value = false
		return toggleSelectAll(true)
	}

	// Handle Ctrl/Cmd+Z (Undo)
	if ((e.metaKey || e.ctrlKey) && key === 'z' && !shouldIgnoreKeypress(e, true)) {
		e.preventDefault()
		isGPressed.value = false
		return undo()
	}

	if (shouldIgnoreKeypress(e)) return

	if (key === 'g') return handleGKeyPress(e)
	if (isGPressed.value) return handleGMenuNavigation(e, key)
	if (key === 'enter') return handleEnter(e)
	if (key === 'escape') return handleEscape(e)
	if (key === '?') return handleShowShortcuts(e)

	const hasSelection = selections.value.length > 0 || threadID
	if (hasSelection) handleThreadActions(e, key)
	handleArrowNavigation(e, key)
}

const handleGKeyPress = (e: KeyboardEvent) => {
	clearTimeout(gPressTimeout.value)

	if (e.shiftKey) {
		const lastThread = threadIDs.value.at(-1)
		if (threadID) return goToThread(lastThread)
		return focusOnThread(lastThread)
	}

	if (isGPressed.value) {
		isGPressed.value = false
		const firstThread = threadIDs.value[0]
		if (threadID) return goToThread(firstThread)
		return focusOnThread(firstThread)
	}

	isGPressed.value = true
	gPressTimeout.value = setTimeout(() => (isGPressed.value = false), 750)
}

const handleGMenuNavigation = (e: KeyboardEvent, key: string) => {
	isGPressed.value = false

	const navigationMap: Record<string, string> = {
		i: mailboxIds.inbox,
		f: 'starred',
		s: mailboxIds.sent,
		d: mailboxIds.drafts,
		j: mailboxIds.junk,
		t: mailboxIds.trash,
	}

	const mailboxId = navigationMap[key]
	if (mailboxId) {
		e.preventDefault()
		router.push({ name: 'Mailbox', params: { mailbox: mailboxId } })
	}
}

const handleShowShortcuts = (e: KeyboardEvent) => {
	e.preventDefault()
	showShortcuts.value = true
}

const handleEnter = (e: KeyboardEvent) => {
	e.preventDefault()
	if (threadInFocus.value) goToThread(threadInFocus.value)
	else focusOnThread(threadIDs.value[0])
}

const handleEscape = (e: KeyboardEvent) => {
	e.preventDefault()
	if (threadID) goToMailbox()
	else if (selections.value.length) resetSelections()
	else threadInFocus.value = undefined
}

const handleThreadActions = (e: KeyboardEvent, key: string) => {
	const thread_ids = selections.value.length ? selections.value : [threadID!]

	// Delete/Trash (Backspace on Mac, Delete on Windows)
	if (key === (isMac ? 'backspace' : 'delete')) {
		e.preventDefault()
		if (e.shiftKey || mailbox === mailboxIds.trash)
			return junkOrDeleteThreads(thread_ids, false)
		return handleMoveThreads({ [mailboxIds.trash]: thread_ids })
	}

	// Mark as junk (!)
	if (key === '!') {
		e.preventDefault()
		return junkOrDeleteThreads(thread_ids, true)
	}

	// Mark as read/unread (u)
	if (key === 'u') {
		e.preventDefault()
		return handleSetSeen({ [Number(e.shiftKey)]: thread_ids })
	}
}

const handleArrowNavigation = (e: KeyboardEvent, key: string) => {
	const navigationKeys = ['arrowup', 'arrowdown', 'j', 'k']
	if (!navigationKeys.includes(key)) return

	e.preventDefault()

	const prevThread = threadInFocus.value
	const offset = ['arrowup', 'k'].includes(key) ? -1 : 1

	let newThread = undefined

	if (threadID) {
		newThread = getThreadByOffset(offset) || threadInFocus.value
		goToThread(newThread)
	} else {
		if (threadIDs.value.includes(threadInFocus.value)) focusOnThreadByOffset(offset)
		else focusOnThread(threadIDs.value[0])
		newThread = threadInFocus.value
	}

	// Handle shift+arrow selection
	if (!(isShiftPressed.value && newThread)) return

	const threadsToToggle = prevThread ? [prevThread, newThread] : [newThread]
	const shouldSelect = !selections.value.includes(newThread)
	toggleSelect(threadsToToggle, shouldSelect, true)
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
			label: __('Mark as Junk (!)'),
			onClick: () => junkOrDeleteThreads(selections.value, true),
			icon: CircleAlert,
			condition:
				!!selections.value.length &&
				mailbox !== mailboxIds.drafts &&
				selections.value.some(
					(threadID) =>
						threadsResource.value?.data?.find((t: Thread) => t.thread_id === threadID)
							?.junk === 0,
				),
		},
		{
			label: __('Mark as Not Junk'),
			onClick: () => handleSetSpamStatus({ 0: selections.value }),
			icon: CircleCheck,
			condition:
				!!selections.value.length &&
				selections.value.some(
					(threadID) =>
						threadsResource.value?.data?.find((t: Thread) => t.thread_id === threadID)
							?.junk === 1,
				),
		},
		{
			label: __('Move to Trash (Delete)'),
			onClick: () => handleMoveThreads({ [mailboxIds.trash]: selections.value }),
			icon: Trash2,
			condition: !!selections.value.length && mailbox !== mailboxIds.trash,
		},
		{
			label: __('Delete Threads (Shift+Delete)'),
			onClick: () => junkOrDeleteThreads(selections.value, false),
			icon: Trash2,
			condition: !!selections.value.length && mailbox === mailboxIds.trash,
		},
		{
			label: __('Mark as Read (Shift+U)'),
			onClick: () => handleSetSeen({ 1: selections.value }),
			icon: MailOpen,
			condition:
				!!selections.value.length &&
				selections.value.some(
					(threadID) =>
						threadsResource.value?.data?.find((t: Thread) => t.thread_id === threadID)
							?.seen === 0,
				),
		},
		{
			label: __('Mark as Unread (U)'),
			onClick: () => handleSetSeen({ 0: selections.value }),
			icon: Mail,
			condition:
				!!selections.value.length &&
				selections.value.some(
					(threadID) =>
						threadsResource.value?.data?.find((t: Thread) => t.thread_id === threadID)
							?.seen === 1,
				),
		},
		{
			label: __('Refresh'),
			onClick: () => reloadThreads(),
			icon: RefreshCw,
			condition: !selections.value.length,
		},
	].filter((action) => action.condition),
)

// Search

const noOfSearchResults = ref(0)

const searchResults = createResource({
	url: 'mail.api.mail.search_mails',
	makeParams: () => ({ filter: route.query, limit: limit.value }),
	transform: (data: [Thread[], number]) => {
		noOfSearchResults.value = data[1]
		return data[0]
	},
})

watch(
	() => JSON.stringify(route.query),
	() => {
		if (mailbox === 'search') {
			limit.value = 50
			searchResults.reload()
		}
	},
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

const threadsResource = computed(() => (mailbox === 'search' ? searchResults : threads))

const threadIDs = computed(
	() => threadsResource.value.data?.map((thread: Thread) => thread.thread_id) || [],
)

const reloadThreads: (reloadMailboxes?: boolean, mailboxRoles?: MailboxRole[]) => void = (
	reloadMailboxes = true,
	mailboxRoles = [],
) => {
	if (mailboxRoles.length && !mailboxRoles.map((m) => mailboxIds[m]).includes(mailbox)) return

	resetSelections()
	threadsResource.value.reload()
	if (reloadMailboxes) mailboxes.reload()
}

watch(
	() => mailbox,
	() => {
		threadsResource.value.data = []
		filter.value = localStorage.getItem(`user:${user.data.name}:filter:${mailbox}`) || null
		limit.value = 50
		threadInFocus.value = undefined
		collapsedGroups.value = []
		reloadThreads(false)
	},
	{ immediate: true },
)

onMounted(() => {
	window.addEventListener('keydown', handleKeyDown)
	window.addEventListener('keyup', handleKeyUp)

	socket.on('new_mail_created', (updatedMailboxes: string[]) => {
		if (updatedMailboxes.includes(mailbox)) reloadThreads()
	})
})

onUnmounted(() => {
	window.removeEventListener('keydown', handleKeyDown)
	window.removeEventListener('keyup', handleKeyUp)
})

const loadMoreThreads = useDebounceFn((e) => {
	const { scrollTop, scrollHeight, clientHeight } = e.target
	if (
		scrollTop + clientHeight >= scrollHeight - 10 &&
		threadsResource.value?.data?.length === limit.value
	) {
		limit.value += 50
		threadsResource.value.reload()
		setTimeout(
			() => e.target.scrollTo({ top: e.target.scrollHeight, behavior: 'smooth' }),
			100,
		)
	}
}, 500)

const goToMailbox = () => router.push({ name: 'Mailbox', params: { mailbox }, query: route.query })

const getThreadByOffset = (offset: number, currentThread: string = threadID!) =>
	threadIDs.value[threadIDs.value.indexOf(currentThread) + offset]

const goToThread = (threadID: string) => {
	if (threadID) router.push({ name: 'Mail', params: { mailbox, threadID }, query: route.query })
}

const goToThreadByOffset = (offset: number) => goToThread(getThreadByOffset(offset))

const focusOnThread = (threadID: string) => {
	if (!threadID) return

	threadInFocus.value = threadID
	scrollIntoView(threadID)
}

const focusOnThreadByOffset = (offset: number) =>
	focusOnThread(getThreadByOffset(offset, threadInFocus.value))

const scrollIntoView = (threadID: string) => {
	const el = mailItems.value?.find((el) => el?.id === threadID)?.$el
	if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

// Actions

type SetSeenParams = {
	0?: string[]
	1?: string[]
}

const setSeen = createResource({
	url: 'mail.api.mail.set_seen',
	makeParams: (thread_ids: SetSeenParams) => ({ thread_ids, mailbox }),
	onSuccess: (thread_ids: SetSeenParams) => {
		mailboxes.reload()
		for (const [seenStr, ids] of Object.entries(thread_ids)) {
			const seen = seenStr === 'true'
			threadsResource.value.data
				.filter((thread: Thread) => ids.includes(thread.thread_id))
				.forEach((thread: Thread) => (thread.seen = seen ? 1 : 0))
			if (
				!seen &&
				threadID &&
				(ids.includes(threadID) ||
					!threadsResource.value.data.some((m: Thread) => ids.includes(m.thread_id)))
			)
				goToMailbox()
		}
	},
})

type MoveThreadsParams = Record<string, string[]>

const moveThreads = createResource({
	url: 'mail.api.mail.set_threads_mailbox',
	makeParams: (thread_ids: MoveThreadsParams) => ({ thread_ids }),
	onSuccess: (thread_ids: string[]) => handleSuccessAndRemoveFromList(thread_ids),
})

const moveToOptions = computed(() =>
	mailboxes.data
		?.filter((m) => ![mailbox, mailboxIds.sent, mailboxIds.drafts].includes(m.id))
		.map((m) => ({
			label: m._name,
			onClick: () => handleMoveThreads({ [m.id]: selections.value }),
		})),
)

const setSpamStatus = createResource({
	url: 'mail.api.mail.set_threads_spam_status',
	makeParams: (thread_ids: SetSeenParams) => ({ thread_ids }),
	onSuccess: (thread_ids: string[]) => handleSuccessAndRemoveFromList(thread_ids),
})

const showJunkOrDeleteThreads = ref(false)
const threadsToBeJunkedOrDeleted = ref<string[]>([])
const isJunkAction = ref(false)

const junkOrDeleteThreads = (threadIDs: string[], isJunk: boolean) => {
	if (!threadIDs?.length) return

	threadsToBeJunkedOrDeleted.value = threadIDs
	isJunkAction.value = isJunk
	showJunkOrDeleteThreads.value = true
}

const junkOrDeleteThreadCount = computed(() => threadsToBeJunkedOrDeleted.value.length)

const junkOrDeleteTitle = computed(() => {
	const count =
		junkOrDeleteThreadCount.value === 1 ? '' : junkOrDeleteThreadCount.value.toString()
	const noun = junkOrDeleteThreadCount.value > 1 ? __('Threads') : __('Thread')

	return isJunkAction.value
		? __('Mark {0} {1} as Junk', [count, noun])
		: __('Delete {0} {1}', [count, noun])
})

const junkOrDeleteMessage = computed(() => {
	const noun = junkOrDeleteThreadCount.value > 1 ? __('threads') : __('thread')

	return isJunkAction.value
		? __('Are you sure you want to mark the selected {0} as junk?', [noun])
		: __('Are you sure you want to permanently delete the selected {0}?', [noun])
})

const handleJunkOrDelete = () => {
	if (isJunkAction.value) handleSetSpamStatus({ 1: threadsToBeJunkedOrDeleted.value })
	else handleDeleteThreads(threadsToBeJunkedOrDeleted.value)

	showJunkOrDeleteThreads.value = false
}

const junkOrDeleteThreadsOptions = computed(() => ({
	title: junkOrDeleteTitle.value,
	message: junkOrDeleteMessage.value,
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: handleJunkOrDelete }],
}))

const deleteThreads = createResource({
	url: 'mail.api.mail.delete_threads',
	makeParams: (thread_ids: string[]) => ({ thread_ids, mailbox }),
	onSuccess: (thread_ids: string[]) => handleSuccessAndRemoveFromList(thread_ids, false),
})

const showEmptyMailbox = ref(false)

const emptyMailbox = createResource({
	url: 'mail.api.mail.empty_user_mailbox',
	makeParams: () => ({ mailbox }),
	onSuccess: () => {
		threadsResource.value.data = []
		raiseToast(__('{0} emptied.', [mailboxName.value]))
		reloadThreads()
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

const handleSuccessAndRemoveFromList = (
	thread_ids: string[] | SetSeenParams,
	excludeCommonMailboxes: boolean = true,
) => {
	reloadThreads()

	if (excludeCommonMailboxes && ['search', 'starred'].includes(mailbox)) return
	if (!Array.isArray(thread_ids)) thread_ids = Object.values(thread_ids).flat()
	if (threadID && thread_ids.includes(threadID))
		if (thread_ids.length === 1) goToThreadByOffset(1)
		else goToMailbox()
	threadsResource.value.data = threadsResource.value.data?.filter(
		(thread: Thread) => !thread_ids.includes(thread.thread_id),
	)
}

// Action handlers

const handleSetSeen = (threadIDs: SetSeenParams, isUndo = false) => {
	const selectedThreads = Object.values(threadIDs).flat()
	const originalState = getOriginalState(selectedThreads, 'seen')
	if (JSON.stringify(originalState) === JSON.stringify(threadIDs)) return

	const action = () => setSeen.submit(threadIDs)
	if (isUndo) return raisePromiseToast(action, __('Undoing...'), __('Read status restored.'))

	setUndoAction(() => handleSetSeen(originalState, true))
	const seen = Object.keys(threadIDs)[0] === '1'
	const loading = seen ? __('Marking as read...') : __('Marking as unread...')
	const success =
		selectedThreads.length === 1
			? __('Thread marked as {0}.', [seen ? __('read') : __('unread')])
			: __('Threads marked as {0}.', [seen ? __('read') : __('unread')])

	raisePromiseToast(action, loading, success, undo)
}

const handleMoveThreads = (threadIDs: Record<string, string[]>, isUndo: boolean = false) => {
	const selectedThreads = Object.values(threadIDs).flat()
	const mailboxMap: Record<string, string> = Object.fromEntries(
		threadsResource.value.data.map((thread: Thread) => [
			thread.thread_id,
			thread['mailboxes'][0].mailbox_id,
		]),
	)
	const originalState: Record<string, string[]> = selectedThreads.reduce(
		(acc: Record<string, string[]>, thread_id: string) => {
			const key = mailboxMap[thread_id]
			if (!acc[key]) acc[key] = []
			acc[key].push(thread_id)
			return acc
		},
		{},
	)
	if (JSON.stringify(originalState) === JSON.stringify(threadIDs)) return

	const action = () => moveThreads.submit(threadIDs)

	if (isUndo) {
		const success =
			selectedThreads.length === 1 ? __('Thread moved back.') : __('Threads moved back.')
		return raisePromiseToast(action, __('Undoing...'), success)
	}

	setUndoAction(() => handleMoveThreads(originalState, true))
	const moveToMailboxName = mailboxes.data?.find((m) => m.id === Object.keys(threadIDs)[0])._name
	const loading = __('Moving to {0}...', [moveToMailboxName])
	const success =
		selectedThreads.length === 1
			? __('Thread moved to {0}.', [moveToMailboxName])
			: __('Threads moved to {0}.', [moveToMailboxName])

	raisePromiseToast(action, loading, success, undo)
}

const handleSetSpamStatus = (threadIDs: SetSeenParams, isUndo = false) => {
	const selectedThreads = Object.values(threadIDs).flat()
	const originalState = getOriginalState(selectedThreads, 'junk')
	if (JSON.stringify(originalState) === JSON.stringify(threadIDs)) return

	const action = () => setSpamStatus.submit(threadIDs)
	if (isUndo) return raisePromiseToast(action, __('Undoing...'), __('Junk status restored.'))

	setUndoAction(() => handleSetSpamStatus(originalState, true))
	const spam = Object.keys(threadIDs)[0] === '1'
	const loading = spam ? __('Marking as Junk...') : __('Marking as Not Junk...')
	const success =
		selectedThreads.length === 1
			? __('Thread marked as {0}.', [spam ? __('Junk') : __('Not Junk')])
			: __('Threads marked as {0}.', [spam ? __('Junk') : __('Not Junk')])

	raisePromiseToast(action, loading, success, undo)
}

const handleDeleteThreads = (thread_ids: string[]) => {
	if (!thread_ids?.length) return

	toast.promise(deleteThreads.submit(thread_ids), {
		loading: __('Deleting...'),
		success: thread_ids.length === 1 ? __('Thread deleted.') : __('Threads deleted.'),
		error: __('Action failed. Please try again in some time.'),
	})
}

const getOriginalState = (
	selectedThreads: string[],
	propertyName: 'seen' | 'junk',
): SetSeenParams => {
	const statusMap: Record<string, 0 | 1> = Object.fromEntries(
		threadsResource.value.data.map((thread: Thread) => [
			thread.thread_id,
			thread[propertyName],
		]),
	)
	const originalState: SetSeenParams = selectedThreads.reduce(
		(acc: SetSeenParams, thread_id: string) => {
			const key = statusMap[thread_id]
			if (!acc[key]) acc[key] = []
			acc[key].push(thread_id)
			return acc
		},
		{},
	)
	return originalState
}

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
const mailboxName = computed(() => {
	switch (mailbox) {
		case 'starred':
			return __('Starred')
		case 'search':
			return __('Search')
		default:
			return mailboxObj.value?._name
	}
})
const noOfThreads = computed(() => {
	if (mailbox === 'search')
		return `${noOfSearchResults.value} ${noOfSearchResults.value == 1 ? __('result') : __('results')}`
	return `${mailboxObj.value?.total_threads} ${mailboxObj.value?.total_threads == 1 ? __('thread') : __('threads')}`
})

const title = computed(() => {
	if (selections.value.length)
		return selections.value.length === 1
			? __('1 item selected')
			: __('{0} items selected', [String(selections.value.length)])

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

<style scoped>
/* Mail item animations */
.mail-item-enter-active {
	@apply transition-all delay-300 duration-300 ease-in-out;
}
.mail-item-enter-from {
	@apply translate-x-5 opacity-0;
}
.mail-item-leave-active {
	@apply transition-all duration-300 ease-in-out;
}
.mail-item-leave-to {
	@apply -translate-x-5 opacity-0;
}
.mail-item-move {
	@apply transition-transform duration-300 ease-in-out;
}

/* Group animations */
.mail-group-enter-active {
	@apply transition-all delay-300 duration-300 ease-in-out;
}
.mail-group-enter-from {
	@apply translate-x-5 opacity-0;
}
.mail-group-leave-active {
	@apply transition-all duration-300 ease-in-out;
}
.mail-group-leave-to {
	@apply -translate-x-5 opacity-0;
}
.mail-group-move {
	@apply transition-transform duration-300 ease-in-out;
}
</style>
