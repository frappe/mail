<template>
	<!-- Header -->
	<header class="flex items-center justify-between border-b px-3 py-2.5 sm:px-5">
		<div class="flex items-center space-x-2">
			<Button v-if="isMobile" icon="menu" variant="ghost" @click="openSidebar" />
			<Breadcrumbs
				:items="[
					{
						label: mailboxName,
						route: { name: 'Mailbox', params: { accountId, mailbox } },
					},
				]"
			/>
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
		<div v-if="isLoading" class="flex w-full flex-col items-center justify-center">
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
				<div
					class="relative flex items-center border-b border-l-transparent px-3.5 py-2.5 sm:border-l sm:px-5"
				>
					<div class="mr-5 max-sm:ml-3">
						<Tooltip
							:text="
								isAllSelected
									? __('Clear All (Esc)')
									: __('Select All ({0}+A)', [modifier])
							"
						>
							<div
								class="checkbox-hitbox -m-3 cursor-pointer p-3"
								@click.stop.prevent="toggleSelectAll(!isAllSelected)"
							>
								<Checkbox
									:model-value="isAllSelected"
									size="md"
									class="pointer-events-none"
								/>
							</div>
						</Tooltip>
					</div>
					<Dropdown
						v-if="!selections.length && mailbox !== 'search'"
						:options="FILTER_OPTIONS"
					>
						<button
							class="text-ink-gray-8 hover:bg-surface-gray-2 -ml-2 flex min-w-0 items-center gap-1 rounded px-2 py-1"
						>
							<span class="truncate">{{ title }}</span>
							<ChevronDown class="text-ink-gray-5 icon shrink-0" />
						</button>
					</Dropdown>
					<p v-else class="pb-[2px]">{{ title }}</p>
					<div class="-mr-1.5 ml-auto flex items-center space-x-1.5 sm:space-x-3">
						<div
							v-if="!selections.length && displayTotal"
							class="text-ink-gray-6 flex items-center gap-1"
						>
							<span class="whitespace-nowrap text-sm tabular-nums">
								{{ range }} {{ __('of') }} {{ totalLabel }}
							</span>
							<Button
								:tooltip="__('Previous Page')"
								variant="ghost"
								:disabled="!canGoPrev"
								@click="goToPage(false)"
							>
								<template #icon>
									<ChevronLeft class="icon" />
								</template>
							</Button>
							<Button
								:tooltip="__('Next Page')"
								variant="ghost"
								:disabled="!canGoNext"
								@click="goToPage(true)"
							>
								<template #icon>
									<ChevronRight class="icon" />
								</template>
							</Button>
						</div>

						<template v-else-if="selections.length">
							<Dropdown v-if="showReadingPane" :options="selectActions">
								<Button variant="ghost" :tooltip="__('Actions')">
									<template #icon>
										<Ellipsis class="icon" />
									</template>
								</Button>
							</Dropdown>
							<template v-else>
								<Button
									v-for="action in selectActions.filter((a) => a.condition())"
									:key="action.label"
									:tooltip="action.label"
									variant="ghost"
									@click="action.onClick"
								>
									<template #icon>
										<component :is="action.icon" class="icon" />
									</template>
								</Button>
							</template>
						</template>

						<Dropdown v-if="showAddTo" :options="addToOptions">
							<Button variant="ghost" :tooltip="__('Add To')">
								<template #icon>
									<component :is="FolderPlus" class="icon" />
								</template>
							</Button>
						</Dropdown>
						<Dropdown v-if="showRemoveFrom" :options="removeFromOptions">
							<Button variant="ghost" :tooltip="__('Remove From')">
								<template #icon>
									<component :is="FolderMinus" class="icon" />
								</template>
							</Button>
						</Dropdown>
						<Dropdown
							v-if="!!selections.length && !['search', 'starred'].includes(mailbox)"
							:options="moveToOptions"
						>
							<Button variant="ghost" :tooltip="__('Move To')">
								<template #icon>
									<component :is="FolderInput" class="icon" />
								</template>
							</Button>
						</Dropdown>
					</div>
					<!-- Subtle loading bar: a segment sliding across the bottom outline (no layout shift) -->
					<div
						v-if="threadsResource?.loading"
						class="loading-bar pointer-events-none absolute bottom-[-1px] left-[-1px] right-0 h-0.5 overflow-hidden"
						role="progressbar"
						aria-busy="true"
					>
						<div
							class="loading-bar__fill via-ink-gray-3 absolute inset-y-0 left-0 w-[30%] bg-gradient-to-r from-transparent to-transparent"
						/>
					</div>
				</div>

				<!-- Mail list -->
				<div
					v-if="threadsResource?.data?.length"
					ref="mailList"
					class="h-full overflow-y-auto overscroll-contain"
				>
					<div v-for="(group, key) in groupedThreads" :key="key">
						<Tooltip
							v-if="groupMessagesBy !== 'None'"
							:text="
								isLastGroup(key)
									? ''
									: __(collapsedGroups.includes(key) ? 'Expand' : 'Collapse')
							"
						>
							<div
								class="text-ink-gray-6 group flex items-center border-b border-l-transparent p-3.5 text-xs font-semibold sm:border-l sm:px-5"
								@click="toggleGroupCollapse(key)"
							>
								<div
									class="pr-7.5 checkbox-hitbox -m-3 cursor-pointer py-3 pl-6 sm:pl-3"
									@click.stop.prevent="
										toggleSelect(getGroupThreads(key), !isGroupSelected(key))
									"
								>
									<Checkbox
										:model-value="isGroupSelected(key)"
										size="md"
										class="pointer-events-none"
									/>
								</div>

								<span class="select-none pt-[2px]">
									{{
										getFormattedDate(
											key,
											groupMessagesBy === 'Month',
										).toUpperCase()
									}}
								</span>

								<component
									:is="
										collapsedGroups.includes(key) ? ChevronRight : ChevronDown
									"
									v-if="!isLastGroup(key)"
									class="icon ml-auto"
								/>
							</div>
						</Tooltip>
						<template v-if="!collapsedGroups.includes(key)">
							<MailListItem
								v-for="mail in group"
								ref="mailItems"
								:key="mail.name"
								:mailbox
								:mail
								:is-selected="selections.includes(mail.thread_id)"
								class="border-l-transparent sm:border-l"
								:class="{
									'!bg-surface-blue-1': mail.thread_id === threadID && !isMobile,
									'!border-l-blue-500': mail.thread_id === threadInFocus,
								}"
								@set-seen="
									(seen: boolean) =>
										handleSetSeen({ [Number(seen)]: [mail.thread_id] })
								"
								@archive-thread="
									mailbox === mailboxIds.sent
										? handleAddThreadsToMailbox(mailboxIds.archive, [
												mail.thread_id,
											])
										: handleMoveThreads({
												[mailboxIds.archive]: [mail.thread_id],
											})
								"
								@trash-thread="
									handleMoveThreads({ [mailboxIds.trash]: [mail.thread_id] })
								"
								@delete-thread="junkOrDeleteThreads([mail.thread_id], false)"
								@set-flagged="
									(flagged: boolean) =>
										setFlaggedByThreadIDs([mail.thread_id], flagged)
								"
								@set-selected="
									(selected: boolean) => toggleSelect([mail.thread_id], selected)
								"
							/>
						</template>
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
					ref="mailThread"
					:mailbox
					:thread-i-d
					:threads="threadIDs"
					:messages="currentThread?.messages"
					:can-go-prev="canGoPrev"
					:can-go-next="canGoNext"
					@reload-mails="reloadThreads"
					@set-seen="
						(seen: boolean, ids: string[]) =>
							handleSetSeen({ [Number(seen)]: [threadID!] }, seen, ids)
					"
					@sync-unseen="handleSyncUnseen"
					@set-flagged="
						(ids: string[], flagged: boolean) => setFlagged.submit({ ids, flagged })
					"
					@move-thread="
						(moveToMailbox: string) =>
							handleMoveThreads({ [moveToMailbox]: [threadID!] })
					"
					@add-thread-to-mailbox="
						(mailboxId: string) => handleAddThreadsToMailbox(mailboxId, [threadID!])
					"
					@remove-thread-from-mailbox="
						(mailboxId: string) =>
							handleRemoveThreadsFromMailbox(mailboxId, [threadID!])
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
	Archive,
	ChevronDown,
	ChevronLeft,
	ChevronRight,
	CircleAlert,
	CircleCheck,
	Ellipsis,
	FolderInput,
	FolderMinus,
	FolderPlus,
	LoaderCircle,
	Mail as MailIcon,
	MailOpen,
	Mails,
	Paperclip,
	RefreshCw,
	Star,
	StarOff,
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
	usePageMeta,
} from 'frappe-ui'

import { getFormattedDate, isMac, raiseToast, shouldIgnoreKeypress, startResizing } from '@/utils'
import { useScreenSize, useSidebar, useUndo } from '@/utils/composables'
import { useThreadActions } from '@/utils/useThreadActions'
import { type MailboxRole, userStore } from '@/stores/user'
import HeaderActions from '@/components/HeaderActions.vue'
import NoMails from '@/components/Icons/NoMails.vue'
import MailListItem from '@/components/MailListItem.vue'
import MailThread from '@/components/MailThread.vue'
import ShortcutsModal from '@/components/Modals/ShortcutsModal.vue'

import type { COLOR_SCHEME, Thread, UserResource } from '@/types'

const { accountId, mailbox, threadID } = defineProps<{
	accountId: string
	mailbox: string
	threadID?: string
}>()

const route = useRoute()
const router = useRouter()
const { isMobile } = useScreenSize()
const { openSidebar } = useSidebar()
const { undo } = useUndo()

const socket = inject('$socket')
const user = inject('$user') as UserResource
const dayjs = inject('$dayjs')

const store = userStore()
const { mailboxes, mailboxIds } = store

// Appearance

const showReadingPane = computed(() => !!user.data?.show_reading_pane)
const groupMessagesBy = computed(() => user.data.group_messages_by)

// Thread Groups

const groupedThreads = computed<Record<string, Thread[]>>(() =>
	threadsResource.value?.data?.reduce((groups: Record<string, Thread[]>, thread: Thread) => {
		const date = dayjs(thread.received_at).format(
			groupMessagesBy.value === 'Day' ? 'YYYY-MM-DD' : 'YYYY-MM',
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

const mailItemsRef = useTemplateRef('mailItems')
const mailThreadRef = useTemplateRef('mailThread')
const mailListRef = useTemplateRef('mailList')

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
const reloadInterval = ref<ReturnType<typeof setInterval>>()

const handleKeyDown = (e: KeyboardEvent) => {
	isShiftPressed.value = e.shiftKey
	const key = e.key.toLowerCase()

	// Handle Ctrl/Cmd+Shift+L (Cycle Theme)
	if ((e.metaKey || e.ctrlKey) && e.shiftKey && key === 'l' && !shouldIgnoreKeypress(e, true)) {
		e.preventDefault()
		isGPressed.value = false
		return cycleTheme()
	}

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
		router.push({ name: 'Mailbox', params: { accountId, mailbox: mailboxId } })
	}
}

const handleShowShortcuts = (e: KeyboardEvent) => {
	e.preventDefault()
	showShortcuts.value = true
}

const COLOR_SCHEME_CYCLE = ['System Default', 'Light Mode', 'Dark Mode'] as const

const cycleTheme = () => {
	const current = user.data.color_scheme
	const idx = COLOR_SCHEME_CYCLE.indexOf(current as COLOR_SCHEME)
	const next = COLOR_SCHEME_CYCLE[(idx + 1) % COLOR_SCHEME_CYCLE.length]
	updateColorScheme.submit(next)
}

const updateColorScheme = createResource({
	url: 'frappe.client.set_value',
	makeParams: (color_scheme: COLOR_SCHEME) => ({
		doctype: 'User Settings',
		name: user.data.user_settings,
		fieldname: { color_scheme },
	}),
	onSuccess: (data) => {
		raiseToast(__('Color scheme updated to {0}.', [data.color_scheme]))
		user.reload()
	},
})

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

	// Mark as read/unread (u)
	if (key === 'u') {
		e.preventDefault()
		return handleSetSeen({ [Number(e.shiftKey)]: thread_ids })
	}

	// Archive (e)
	if (key === 'e') {
		e.preventDefault()
		return mailbox === mailboxIds.sent
			? handleAddThreadsToMailbox(mailboxIds.archive, thread_ids)
			: handleMoveThreads({ [mailboxIds.archive]: thread_ids })
	}

	// Mark as junk (!)
	if (key === '!') {
		e.preventDefault()
		return junkOrDeleteThreads(thread_ids, true)
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
	condition: () => boolean
}

const selectActions = computed((): SelectAction[] => [
	{
		label: __('Star Mails'),
		onClick: () => setFlaggedByThreadIDs(selections.value, true),
		icon: Star,
		condition: () =>
			selections.value.some(
				(threadID) =>
					threadsResource.value?.data?.find((t: Thread) => t.thread_id === threadID)
						?.flagged === 0,
			),
	},
	{
		label: __('Unstar Mails'),
		onClick: () => setFlaggedByThreadIDs(selections.value, false),
		icon: StarOff,
		condition: () =>
			selections.value.some(
				(threadID) =>
					threadsResource.value?.data?.find((t: Thread) => t.thread_id === threadID)
						?.flagged === 1,
			),
	},
	{
		label: __('Mark as Read (Shift+U)'),
		onClick: () => handleSetSeen({ 1: selections.value }),
		icon: MailOpen,
		condition: () =>
			selections.value.some(
				(threadID) =>
					threadsResource.value?.data?.find((t: Thread) => t.thread_id === threadID)
						?.seen === 0,
			),
	},
	{
		label: __('Mark as Unread (U)'),
		onClick: () => handleSetSeen({ 0: selections.value }),
		icon: MailIcon,
		condition: () =>
			selections.value.some(
				(threadID) =>
					threadsResource.value?.data?.find((t: Thread) => t.thread_id === threadID)
						?.seen === 1,
			),
	},
	{
		label: __('Archive Threads (E)'),
		onClick: () =>
			mailbox === mailboxIds.sent
				? handleAddThreadsToMailbox(mailboxIds.archive, selections.value)
				: handleMoveThreads({ [mailboxIds.archive]: selections.value }),
		icon: Archive,
		condition: () => mailbox !== mailboxIds.archive,
	},
	{
		label: __('Mark as Junk (!)'),
		onClick: () => junkOrDeleteThreads(selections.value, true),
		icon: CircleAlert,
		condition: () =>
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
		condition: () =>
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
		condition: () => mailbox !== mailboxIds.trash,
	},
	{
		label: __('Delete Threads (Shift+Delete)'),
		onClick: () => junkOrDeleteThreads(selections.value, false),
		icon: Trash2,
		condition: () => mailbox === mailboxIds.trash,
	},
])

// Search

// Pagination state (shared by the threads and search resources — only one is active at a time)
const PAGE_LENGTH = 25
const page = ref(0) // navigation target: the page being fetched
const displayedPage = ref(0) // the page currently shown; lags `page` until its data loads
const total = ref(0) // exact total matching the current view (search only)
const hasMore = ref(false) // lookahead: an extra row was returned, so a next page exists
// Current mailbox's record (carries total_threads/unread_threads). Declared here because the threads
// resource's makeParams reads it during setup (via the immediate watch), before its later UI uses.
const mailboxObj = computed(() => mailboxes.data?.find((m) => m.id === mailbox))

// Called once a page's data has loaded: reveal it (range + list update together) and scroll to top.
// No-op for same-page reloads (e.g. the periodic refresh) so those don't yank the scroll position.
const syncDisplayedPage = () => {
	if (displayedPage.value === page.value) return
	displayedPage.value = page.value
	mailListRef.value?.scrollTo({ top: 0 })
}

const searchResults = createResource({
	url: 'mail.api.mail.search_mails',
	makeParams: () => ({
		account: store.account,
		filter: route.query,
		limit: PAGE_LENGTH,
		start: page.value * PAGE_LENGTH,
	}),
	transform: (data: [Thread[], number]) => {
		total.value = data[1]
		return data[0]
	},
	onSuccess: (data: [Thread[], number]) => {
		correctPageOverflow(data[0])
		openPendingEdgeThread()
		syncDisplayedPage()
		if (mailbox === 'search') isMailboxLoaded.value = true
	},
})

watch(
	() => JSON.stringify(route.query),
	() => {
		if (mailbox === 'search') {
			page.value = 0
			searchResults.reload()
		}
	},
)

// Main data

const filter = ref<string | null>(
	localStorage.getItem(`user:${user.data.name}:filter:${mailbox}`) || null,
)
const isMailboxLoaded = ref(false)

const threads = createResource({
	url: 'mail.api.mail.get_threads',
	makeParams: () => ({
		account: store.account,
		mailbox,
		limit: threadsLimit.value,
		start: page.value * PAGE_LENGTH,
		filter_by: filter.value,
	}),
	transform: (data: [Thread[], string]) => {
		const rows = data[0]
		// The extra (PAGE_LENGTH + 1)th row only signals a next page — drop it from the display.
		if (countMode.value === 'lookahead') {
			hasMore.value = rows.length > PAGE_LENGTH
			return rows.slice(0, PAGE_LENGTH)
		}
		hasMore.value = false
		return rows
	},
	onSuccess: (data: [Thread[], string]) => {
		correctPageOverflow(data[0])
		openPendingEdgeThread()
		syncDisplayedPage()
		if (mailbox === data[1]) isMailboxLoaded.value = true
	},
})

const threadsResource = computed(() => (mailbox === 'search' ? searchResults : threads))

// If a page ends up empty because threads were removed (e.g. deleted/moved), step back a page.
// Decrementing one at a time is bounded by 0, so it can't loop even if `total` is stale.
const correctPageOverflow = (pageData: Thread[]) => {
	if (pageData.length || page.value === 0) return
	page.value -= 1
	threadsResource.value.reload()
}

const threadsOnPage = computed(() => threadsResource.value.data?.length ?? 0)

// How the total count and "next page" are resolved:
// - 'exact'     (search): the backend returns the exact total.
// - 'mailbox'   (a plain mailbox, no filter): use the mailbox's stored thread count.
// - 'lookahead' (a filtered mailbox, or the cross-mailbox "starred" view): no cheap total exists, so
//   we fetch one extra row (PAGE_LENGTH + 1). The extra row means a next page exists; we show the
//   running count with a "+" suffix and only enable Next while it's present.
const countMode = computed<'exact' | 'mailbox' | 'lookahead'>(() => {
	if (mailbox === 'search') return 'exact'
	if (mailbox === 'starred' || filter.value) return 'lookahead'
	return 'mailbox'
})
const mailboxTotal = computed(() => mailboxObj.value?.total_threads ?? 0)

// Rows to request for the current page. In 'lookahead' mode fetch one extra row to detect a next
// page; in 'mailbox' mode never fetch past the known total, so the last page returns only the
// remainder (avoids overshooting, e.g. "26–50 of 41"). Falls back to a full page until the total loads.
const threadsLimit = computed(() => {
	if (countMode.value === 'lookahead') return PAGE_LENGTH + 1
	if (countMode.value === 'mailbox' && mailboxTotal.value > 0) {
		return Math.min(PAGE_LENGTH, Math.max(0, mailboxTotal.value - page.value * PAGE_LENGTH))
	}
	return PAGE_LENGTH
})

// The fixed total for the current view, if known (null in lookahead mode, where we only know a lower
// bound). Used to clamp the displayed range so it never overshoots — during a page change the previous
// page's rows linger until the new page loads, which would otherwise read as "26–50 of 41".
const knownTotal = computed<number | null>(() => {
	if (countMode.value === 'exact') return total.value
	if (countMode.value === 'mailbox') return mailboxTotal.value
	return null
})

const rangeEnd = computed(() => {
	// Based on the displayed (loaded) page, not the navigation target, so the range only moves once the
	// new page's data arrives. For a known total, derive the end from the page bounds (clamped to the
	// total) rather than the row count; the fetch is clamped to the same bound, so it matches the loaded
	// page while staying stable during a page change, when the previous page's rows still linger.
	if (knownTotal.value && knownTotal.value > 0) {
		return Math.min((displayedPage.value + 1) * PAGE_LENGTH, knownTotal.value)
	}
	return displayedPage.value * PAGE_LENGTH + threadsOnPage.value
})
const rangeStart = computed(() =>
	rangeEnd.value === 0 ? 0 : displayedPage.value * PAGE_LENGTH + 1,
)
// Collapse to a single number when the page holds one thread (e.g. "1" instead of "1–1").
const range = computed(() =>
	rangeStart.value === rangeEnd.value
		? `${rangeStart.value}`
		: `${rangeStart.value}–${rangeEnd.value}`,
)
const displayTotal = computed(() =>
	countMode.value === 'lookahead' ? rangeEnd.value : (knownTotal.value ?? 0),
)
// In lookahead mode the count is a lower bound — show "n+" while a next page exists, else "n".
const totalLabel = computed(() =>
	countMode.value === 'lookahead'
		? `${rangeEnd.value}${hasMore.value ? '+' : ''}`
		: `${displayTotal.value}`,
)

// Prev/Next are bounded by the navigation target (`page`), not the displayed page, so presses can be
// queued while a page is still loading. Lookahead only knows one page ahead exists, so it can't queue
// past the loaded page.
const canGoPrev = computed(() => page.value > 0)
const canGoNext = computed(() =>
	countMode.value === 'lookahead'
		? hasMore.value && page.value === displayedPage.value
		: (page.value + 1) * PAGE_LENGTH < (knownTotal.value ?? 0),
)

// Coalesce rapid Prev/Next presses: only the final target page is fetched, and the displayed page
// (range + list) updates once it loads — intermediate pages are never shown.
const navigate = useDebounceFn(() => threadsResource.value.reload(), 250)

const goToPage = (next: boolean) => {
	if (next ? !canGoNext.value : !canGoPrev.value) return
	page.value += next ? 1 : -1
	resetSelections()
	navigate()
}

const isLoading = computed(() => {
	if (!isMailboxLoaded.value) return true
	if (emptyMailbox.loading) return true
	return !threadsResource.value.data.length && threadsResource.value?.loading
})

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
	() => [mailbox, accountId],
	() => {
		isMailboxLoaded.value = false
		threadsResource.value.data = []
		filter.value = localStorage.getItem(`user:${user.data.name}:filter:${mailbox}`) || null
		page.value = 0
		threadInFocus.value = undefined
		collapsedGroups.value = []
		reloadThreads(false)
	},
	{ immediate: true },
)

onMounted(() => {
	window.addEventListener('keydown', handleKeyDown)
	window.addEventListener('keyup', handleKeyUp)
	reloadInterval.value = setInterval(() => threadsResource.value.reload(), 30000)

	socket.on('new_mail_created', (updatedMailboxes: string[]) => {
		if (updatedMailboxes.includes(mailbox)) threadsResource.value.reload()
	})

	socket.on('mail_exchange_completed', (payload: { success: boolean; message: string }) =>
		raiseToast(payload.message, payload.success ? 'success' : 'error'),
	)
})

onUnmounted(() => {
	window.removeEventListener('keydown', handleKeyDown)
	window.removeEventListener('keyup', handleKeyUp)
	if (reloadInterval.value) clearInterval(reloadInterval.value)
})

const goToMailbox = () =>
	router.push({ name: 'Mailbox', params: { accountId, mailbox }, query: route.query })

const getThreadByOffset = (offset: number, currentThread: string = threadID!) =>
	threadIDs.value[threadIDs.value.indexOf(currentThread) + offset]

const goToThread = (threadID: string) => {
	if (threadID)
		router.push({ name: 'Mail', params: { accountId, mailbox, threadID }, query: route.query })
}

// When stepping past the first/last thread of a page, move to the adjacent page (if any) and open
// its edge thread once the new page has loaded (`openPendingEdgeThread`, called from onSuccess).
let pendingEdgeThread: 'first' | 'last' | null = null

const goToThreadByOffset = (offset: number) => {
	const next = getThreadByOffset(offset)
	if (next) return goToThread(next)

	if (offset > 0 && canGoNext.value) {
		pendingEdgeThread = 'first'
		goToPage(true)
	} else if (offset < 0 && canGoPrev.value) {
		pendingEdgeThread = 'last'
		goToPage(false)
	}
}

const openPendingEdgeThread = () => {
	if (!pendingEdgeThread) return
	const id = pendingEdgeThread === 'first' ? threadIDs.value[0] : threadIDs.value.at(-1)
	if (!id) return // keep the flag if the page is still empty (e.g. after overflow correction)
	pendingEdgeThread = null
	goToThread(id)
}

const goToNextThreadOrMailbox = (excludedThreads: string[] = []) => {
	const idx = threadIDs.value.indexOf(threadID)
	const next = threadIDs.value.slice(idx + 1).find((id) => !excludedThreads.includes(id))
	if (next) goToThread(next)
	else goToMailbox()
}

const focusOnThread = (threadID: string) => {
	if (!threadID) return

	threadInFocus.value = threadID
	scrollIntoView(threadID)
}

const focusOnThreadByOffset = (offset: number) =>
	focusOnThread(getThreadByOffset(offset, threadInFocus.value))

const scrollIntoView = (threadID: string) => {
	const el = mailItemsRef.value?.find((el) => el?.id === threadID)?.$el
	if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

// Actions

const {
	handleSetSeen,
	handleSyncUnseen,
	setFlaggedByThreadIDs,
	handleMoveThreads,
	handleSetSpamStatus,
	handleAddThreadsToMailbox,
	handleRemoveThreadsFromMailbox,
	junkOrDeleteThreads,
	setFlagged,
	moveToOptions,
	addToOptions,
	removeFromOptions,
	showAddTo,
	showRemoveFrom,
	showJunkOrDeleteThreads,
	junkOrDeleteThreadsOptions,
} = useThreadActions({
	threadsResource,
	mailbox: computed(() => mailbox),
	threadID: computed(() => threadID),
	selections,
	mailThreadRef,
	reloadThreads,
	goToMailbox,
	goToNextThreadOrMailbox,
})

const showEmptyMailbox = ref(false)

const emptyMailbox = createResource({
	url: 'mail.api.mail.empty_user_mailbox',
	makeParams: () => ({ account: store.account, mailbox }),
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

// Filter

const FILTER_OPTIONS = [
	{
		label: __('All'),
		icon: Mails,
		onClick: () => setFilter(null),
	},
	{
		label: __('Unread'),
		icon: MailIcon,
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
	page.value = 0
	threads.reload()
	resetSelections()
}

// UI formatting

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
const unreadThreadsPrefix = computed(() =>
	mailboxObj.value?.unread_threads ? `(${mailboxObj.value.unread_threads})` : '',
)

const currentThread = computed(() =>
	threadsResource.value?.data?.find((t: Thread) => t.thread_id === threadID),
)

usePageMeta(() => {
	if (threadID) return { title: currentThread.value?.subject || __('[No Subject]') }
	return { title: `${unreadThreadsPrefix.value} ${mailboxName.value}` }
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
			return __('With Attachments')
		default:
			return __('All Mails')
	}
})
</script>

<style scoped>
.checkbox-hitbox:hover :deep(input[type='checkbox']) {
	@apply border-outline-gray-5 shadow-sm;
}

.loading-bar__fill {
	animation: loading-bar-slide 1.2s linear infinite;
}

@keyframes loading-bar-slide {
	0% {
		transform: translateX(-100%);
	}
	100% {
		transform: translateX(333%);
	}
}
</style>
