import { type ComputedRef, type Ref, computed, h, ref } from 'vue'
import { Icon } from 'frappe-ui/icons'
import { createResource, toast } from 'frappe-ui'

import { FOLDER_ICON_COLOR_MAP } from '@/constants'
import { getIcon, raisePromiseToast, raiseToast } from '@/utils'
import { useUndo } from '@/utils/composables'
import { userStore } from '@/stores/user'

import type { Mail, Thread } from '@/types'

export type SetSeenParams = {
	0?: string[]
	1?: string[]
}

interface ThreadsResource {
	data: Thread[]
	reload: () => void
}

interface MailThreadInstance {
	syncFlagged: (ids: string[], flagged: boolean) => void
	syncMailboxMembership: (mailboxId: string, isMember: boolean) => void
}

/**
 * List/reading-pane thread actions performed directly on mail ids (the full thread is loaded, so the
 * server doesn't need to resolve thread ids). Optimistic UI, undo and toasts live here too.
 */
export function useThreadActions(deps: {
	threadsResource: ComputedRef<ThreadsResource>
	mailbox: ComputedRef<string>
	threadID: ComputedRef<string>
	selections: Ref<string[]>
	mailThreadRef: Ref<MailThreadInstance | null>
	reloadThreads: (reloadMailboxes?: boolean, mailboxRoles?: string[]) => void
	goToMailbox: () => void
	goToNextThreadOrMailbox: (excludedThreads?: string[]) => void
}) {
	const {
		threadsResource,
		mailbox,
		threadID,
		selections,
		mailThreadRef,
		reloadThreads,
		goToMailbox,
		goToNextThreadOrMailbox,
	} = deps

	const store = userStore()
	const { mailboxes, mailboxIds } = store
	const { setUndoAction, undo } = useUndo()

	const threadMails = (threadIds: string[]): Mail[] => {
		const items = (threadsResource.value.data ?? []).filter((t: Thread) =>
			threadIds.includes(t.thread_id),
		)
		// In search, each result is itself a mail with no nested conversation.
		if (mailbox.value === 'search') return items as unknown as Mail[]
		return items.flatMap((t: Thread) => t.messages ?? [])
	}

	const isSentMail = (m: Mail) => m.mailboxes.some((mb) => mb.mailbox_id === mailboxIds.sent)

	const allMailIds = (threadIds: string[]): string[] => threadMails(threadIds).map((m) => m.id)

	// Mails of the threads that live in the current view's mailbox(es) — mirrors the old
	// get_filtered_message_ids (starred → all non-trash, search → all).
	const currentMailboxMails = (threadIds: string[]): Mail[] => {
		const mails = threadMails(threadIds)
		if (mailbox.value === 'search') return mails
		const ids =
			mailbox.value === 'starred'
				? (mailboxes.data ?? []).filter((m) => m.role !== 'trash').map((m) => m.id)
				: [mailbox.value]
		return mails.filter((m) => m.mailboxes.some((mb) => ids.includes(mb.mailbox_id)))
	}

	const setSeen = createResource({
		url: 'mail.api.mail.set_mails_seen',
		makeParams: ({ ids, seen }: { ids: string[]; seen: boolean }) => ({
			account: store.account,
			ids,
			seen,
		}),
		onSuccess: () => mailboxes.reload(),
	})

	const setFlagged = createResource({
		url: 'mail.api.mail.set_flagged',
		makeParams: ({ ids, flagged }: { ids: string[]; flagged: boolean }) => ({
			account: store.account,
			ids,
			flagged,
		}),
		onSuccess: ({ ids, flagged }: { ids: string[]; flagged: boolean }) => {
			ids.forEach((id) => {
				const thread = threadsResource.value.data?.find((t: Thread) => t.id === id)
				if (thread) thread.flagged = flagged ? 1 : 0
			})
			if (threadID.value) mailThreadRef.value?.syncFlagged(ids, flagged)
		},
		onError: (error) => raiseToast(error.messages[0], 'error'),
	})

	const moveMails = createResource({
		url: 'mail.api.mail.move_mails',
		makeParams: ({
			ids,
			mailbox: target,
			clear_junk,
		}: {
			ids: string[]
			mailbox: string
			clear_junk?: boolean
		}) => ({ account: store.account, ids, mailbox: target, clear_junk }),
	})

	const moveToOptions = computed(() =>
		mailboxes.data
			?.filter((m) => ![mailbox.value, mailboxIds.sent, mailboxIds.drafts].includes(m.id))
			.map((m) => ({
				label: m._name,
				icon: h(Icon, { name: getIcon(m), class: FOLDER_ICON_COLOR_MAP[m.color] }),
				onClick: () => handleMoveThreads({ [m.id]: selections.value }),
			})),
	)

	const addMails = createResource({
		url: 'mail.api.mail.add_mails_to_mailbox',
		makeParams: ({ ids, mailbox_id }: { ids: string[]; mailbox_id: string }) => ({
			account: store.account,
			ids,
			mailbox_id,
		}),
	})

	const removeMails = createResource({
		url: 'mail.api.mail.remove_mails_from_mailbox',
		makeParams: ({ ids, mailbox_id }: { ids: string[]; mailbox_id: string }) => ({
			account: store.account,
			ids,
			mailbox_id,
		}),
	})

	const showAddTo = computed(
		() =>
			selections.value.length &&
			addToOptions.value.length &&
			!['search', 'starred', mailboxIds.junk, mailboxIds.trash].includes(mailbox.value),
	)

	const showRemoveFrom = computed(
		() =>
			showAddTo.value &&
			threadsResource.value.data
				?.filter((t: Thread) => selections.value.includes(t.thread_id))
				.some((t: Thread) => t.mailboxes.length > 1),
	)

	const addToOptions = computed(() =>
		mailboxes.data
			?.filter((m) => !m.role || ['inbox', 'archive'].includes(m.role))
			.filter((m) => {
				const selected = threadsResource.value.data?.filter((t: Thread) =>
					selections.value.includes(t.thread_id),
				)
				return !selected?.every((t: Thread) =>
					t.mailboxes.some((mb) => mb.mailbox_id === m.id),
				)
			})
			.map((m) => ({
				label: m._name,
				icon: h(Icon, { name: getIcon(m), class: FOLDER_ICON_COLOR_MAP[m.color] }),
				onClick: () => handleAddThreadsToMailbox(m.id, selections.value),
			})),
	)

	const handleAddThreadsToMailbox = (mailboxId: string, threadIds: string[], isUndo = false) => {
		const mailboxName = mailboxes.data?.find((m) => m.id === mailboxId)?._name
		const action = async () => {
			await addMails.submit({ ids: allMailIds(threadIds), mailbox_id: mailboxId })
			reloadThreads()
			if (threadID.value && threadIds.includes(threadID.value))
				mailThreadRef.value?.syncMailboxMembership(mailboxId, true)
		}

		if (isUndo) {
			const success =
				threadIds.length === 1 ? __('Thread added back.') : __('Threads added back.')
			return raisePromiseToast(action, __('Undoing...'), success)
		}

		setUndoAction(() => handleRemoveThreadsFromMailbox(mailboxId, threadIds, true))
		const loading = __('Adding to {0}...', [mailboxName])
		const success =
			threadIds.length === 1
				? __('Thread added to {0}.', [mailboxName])
				: __('Threads added to {0}.', [mailboxName])
		raisePromiseToast(action, loading, success, undo)
	}

	const removeFromOptions = computed(() => {
		const selected = threadsResource.value.data?.filter((t: Thread) =>
			selections.value.includes(t.thread_id),
		)
		const unionMailboxIds = selected
			.map((t: Thread) => new Set(t.mailboxes.map((mb) => mb.mailbox_id)))
			.reduce(
				(union: Set<string>, set: Set<string>) => new Set([...union, ...set]),
				new Set<string>(),
			)
		return mailboxes.data
			?.filter(
				(m) =>
					unionMailboxIds.has(m.id) &&
					![mailboxIds.sent, mailboxIds.drafts].includes(m.id),
			)
			.map((m) => ({
				label: m._name,
				icon: h(Icon, { name: getIcon(m), class: FOLDER_ICON_COLOR_MAP[m.color] }),
				onClick: () => handleRemoveThreadsFromMailbox(m.id, selections.value),
			}))
	})

	const handleRemoveThreadsFromMailbox = (
		mailboxId: string,
		threadIds: string[],
		isUndo = false,
	) => {
		const threadIdsToBeUpdated = threadIds.filter((threadId) => {
			const thread = threadsResource.value.data?.find(
				(t: Thread) => t.thread_id === threadId,
			)
			return thread?.mailboxes.some((mb) => mb.mailbox_id === mailboxId)
		})

		const action = async () => {
			const ids = threadMails(threadIdsToBeUpdated)
				.filter((m) => m.mailboxes.some((mb) => mb.mailbox_id === mailboxId))
				.map((m) => m.id)
			await removeMails.submit({ ids, mailbox_id: mailboxId })
			reloadThreads()
			if (threadID.value && threadIdsToBeUpdated.includes(threadID.value)) {
				if (mailboxId === mailbox.value) goToNextThreadOrMailbox(threadIdsToBeUpdated)
				else mailThreadRef.value?.syncMailboxMembership(mailboxId, false)
			}
		}

		const mailboxName = mailboxes.data?.find((m) => m.id === mailboxId)?._name
		const success =
			threadIdsToBeUpdated.length === 1
				? __('Thread removed from {0}.', [mailboxName])
				: __('Threads removed from {0}.', [mailboxName])

		if (isUndo) return raisePromiseToast(action, __('Undoing...'), success)

		setUndoAction(() => handleAddThreadsToMailbox(mailboxId, threadIdsToBeUpdated, true))
		const loading = __('Removing from {0}...', [mailboxName])
		raisePromiseToast(action, loading, success, undo)
	}

	const setMailsSpam = createResource({
		url: 'mail.api.mail.set_mails_spam_status',
		makeParams: ({ ids, spam }: { ids: string[]; spam: boolean }) => ({
			account: store.account,
			ids,
			spam,
		}),
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
		actions: [
			{
				label: __('Confirm'),
				variant: 'solid',
				autofocus: true,
				onClick: handleJunkOrDelete,
			},
		],
	}))

	const bulkDelete = createResource({
		url: 'mail.client.doctype.mail_message.mail_message.bulk_delete',
		makeParams: ({ names }: { names: string[] }) => ({ names }),
	})

	const handleSuccessAndRemoveFromList = (
		thread_ids: string[] | SetSeenParams,
		excludeCommonMailboxes: boolean = true,
	) => {
		reloadThreads()

		if (excludeCommonMailboxes && ['search', 'starred'].includes(mailbox.value)) return
		if (!Array.isArray(thread_ids)) thread_ids = Object.values(thread_ids).flat()
		if (threadID.value && thread_ids.includes(threadID.value))
			goToNextThreadOrMailbox(thread_ids)
		threadsResource.value.data = threadsResource.value.data?.filter(
			(thread: Thread) => !thread_ids.includes(thread.thread_id),
		)
	}

	const handleSetSeen = (threadIDs: SetSeenParams, silent = false, mailIds?: string[]) => {
		const seen = Object.keys(threadIDs)[0] === '1'
		const selectedThreads = Object.values(threadIDs).flat()
		// The reading pane passes explicit ids and has already decided a change is needed; the thread-level
		// `seen` flag only reflects the current mailbox, so it can't gate a whole-conversation update.
		if (
			!mailIds &&
			selectedThreads.every(
				(thread_id) =>
					threadsResource.value?.data?.find((t: Thread) => t.thread_id === thread_id)
						?.seen === (seen ? 1 : 0),
			)
		)
			return

		// Apply optimistically so a quick reopen sees the new seen state immediately — waiting for the
		// server round-trip would leave the thread's messages stale (no auto mark-as-read / unseen marker).
		// (No-op for threads not in the list, e.g. ones opened via the get_thread fallback.)
		threadsResource.value.data
			?.filter((t: Thread) => selectedThreads.includes(t.thread_id))
			.forEach((t: Thread) => {
				t.seen = seen ? 1 : 0
				t.messages?.forEach((message) => (message.seen = seen ? 1 : 0))
			})
		if (!seen && threadID.value && selectedThreads.includes(threadID.value)) goToMailbox()

		// Seen applies to the whole conversation (every mailbox) so the state stays consistent. Prefer
		// the open thread's mail ids from the reading pane (covers fallback threads not in the list).
		const ids = mailIds ?? allMailIds(selectedThreads)

		// The auto mark-as-read on opening a thread is silent (no toast).
		if (silent) return void setSeen.submit({ ids, seen })

		const loading = seen ? __('Marking as read...') : __('Marking as unread...')
		const success =
			selectedThreads.length === 1
				? __('Thread marked as {0}.', [seen ? __('read') : __('unread')])
				: __('Threads marked as {0}.', [seen ? __('read') : __('unread')])

		raisePromiseToast(() => setSeen.submit({ ids, seen }), loading, success)
	}

	// "Mark Unread from Here" (set_mails_seen) marks individual messages unread. Sync those message ids
	// onto each thread's nested messages so reopening reads the fresh state without a full reload.
	const handleSyncUnseen = (ids: string[]) => {
		threadsResource.value.data?.forEach((thread: Thread) => {
			// Search results are flat mails with no nested messages — match on the result's own id.
			if (!thread.messages?.length) {
				if (ids.includes(thread.id)) thread.seen = 0
				return
			}
			let changed = false
			thread.messages.forEach((message) => {
				if (ids.includes(message.id)) {
					message.seen = 0
					changed = true
				}
			})
			if (changed) thread.seen = 0
		})
	}

	const setFlaggedByThreadIDs = (threadIDs: string[], flagged: boolean) => {
		setUndoAction(undefined)
		const ids = threadsResource.value.data
			.filter((t: Thread) => threadIDs.includes(t.thread_id))
			.map((t: Thread) => t.id)
		setFlagged.submit({ ids, flagged })
	}

	// Moving keeps Sent copies in place: non-sent mails are moved, sent mails are only added to the
	// target — except for junk/trash, which move everything.
	const handleMoveThreads = (threadIDs: Record<string, string[]>) => {
		const selectedThreads = Object.values(threadIDs).flat()
		if (!selectedThreads.length) return

		const originOf = (tid: string): string | undefined =>
			threadsResource.value.data?.find((t: Thread) => t.thread_id === tid)?.mailboxes[0]
				?.mailbox_id

		const originalState: Record<string, string[]> = selectedThreads.reduce(
			(acc: Record<string, string[]>, tid: string) => {
				const key = originOf(tid)
				if (key) (acc[key] ??= []).push(tid)
				return acc
			},
			{} as Record<string, string[]>,
		)
		if (JSON.stringify(originalState) === JSON.stringify(threadIDs)) return

		const movesAll = (t: string) => [mailboxIds.junk, mailboxIds.trash].includes(t)

		// Plan the forward + reverse mail operations now, while the threads are still in the list.
		const forward: Array<() => Promise<unknown>> = []
		const reverse: Array<() => Promise<unknown>> = []

		for (const [target, tids] of Object.entries(threadIDs)) {
			const mails = threadMails(tids)
			const ids = mails.map((m) => m.id)
			const sentIds = mails.filter(isSentMail).map((m) => m.id)
			const nonSentIds = mails.filter((m) => !isSentMail(m)).map((m) => m.id)

			const nonSentByOrigin: Record<string, string[]> = {}
			tids.forEach((tid) => {
				const origin = originOf(tid)
				if (!origin) return
				const tidNonSent = threadMails([tid])
					.filter((m) => !isSentMail(m))
					.map((m) => m.id)
				if (tidNonSent.length) (nonSentByOrigin[origin] ??= []).push(...tidNonSent)
			})
			const restoreNonSent = () =>
				Promise.all(
					Object.entries(nonSentByOrigin).map(([origin, oids]) =>
						moveMails.submit({ ids: oids, mailbox: origin }),
					),
				)

			if (target === mailboxIds.junk) {
				forward.push(() => setMailsSpam.submit({ ids, spam: true }))
				reverse.push(async () => {
					await setMailsSpam.submit({ ids, spam: false })
					await restoreNonSent()
				})
			} else if (target === mailboxIds.trash) {
				forward.push(() => moveMails.submit({ ids, mailbox: target, clear_junk: true }))
				reverse.push(async () => {
					await restoreNonSent()
					if (sentIds.length)
						await moveMails.submit({ ids: sentIds, mailbox: mailboxIds.sent })
				})
			} else {
				if (nonSentIds.length)
					forward.push(() =>
						moveMails.submit({ ids: nonSentIds, mailbox: target, clear_junk: true }),
					)
				if (sentIds.length)
					forward.push(() => addMails.submit({ ids: sentIds, mailbox_id: target }))
				reverse.push(async () => {
					await removeMails.submit({ ids, mailbox_id: target })
					await restoreNonSent()
				})
			}
		}

		// In Sent, a non-junk/trash move only adds the (sent) copies elsewhere, so the threads stay here.
		const keptInList =
			mailbox.value === mailboxIds.sent && Object.keys(threadIDs).every((t) => !movesAll(t))

		const action = async () => {
			for (const op of forward) await op()
			if (keptInList) reloadThreads()
			else handleSuccessAndRemoveFromList(threadIDs)
		}

		setUndoAction(() => {
			const undoAction = async () => {
				for (const op of reverse) await op()
				reloadThreads()
			}
			raisePromiseToast(
				undoAction,
				__('Undoing...'),
				selectedThreads.length === 1
					? __('Thread moved back.')
					: __('Threads moved back.'),
			)
		})

		const moveToMailboxName = mailboxes.data?.find(
			(m) => m.id === Object.keys(threadIDs)[0],
		)?._name
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

		const spam = Object.keys(threadIDs)[0] === '1'
		// Capture the mail ids now; the threads leave the list on success, so undo can't recompute them.
		const ids = allMailIds(selectedThreads)
		const action = async () => {
			await setMailsSpam.submit({ ids, spam })
			handleSuccessAndRemoveFromList(threadIDs)
		}
		if (isUndo) return raisePromiseToast(action, __('Undoing...'), __('Junk status restored.'))

		setUndoAction(() => {
			const undoAction = async () => {
				await setMailsSpam.submit({ ids, spam: !spam })
				reloadThreads()
			}
			raisePromiseToast(undoAction, __('Undoing...'), __('Junk status restored.'))
		})
		const loading = spam ? __('Marking as Junk...') : __('Marking as Not Junk...')
		const success =
			selectedThreads.length === 1
				? __('Thread marked as {0}.', [spam ? __('Junk') : __('Not Junk')])
				: __('Threads marked as {0}.', [spam ? __('Junk') : __('Not Junk')])

		raisePromiseToast(action, loading, success, undo)
	}

	const handleDeleteThreads = (thread_ids: string[]) => {
		if (!thread_ids?.length) return

		const names = currentMailboxMails(thread_ids).map((m) => m.name)
		toast.promise(
			bulkDelete
				.submit({ names })
				.then(() => handleSuccessAndRemoveFromList(thread_ids, false)),
			{
				loading: __('Deleting...'),
				success: thread_ids.length === 1 ? __('Thread deleted.') : __('Threads deleted.'),
				error: __('Action failed. Please try again in some time.'),
			},
		)
	}

	const getOriginalState = (
		selectedThreads: string[],
		propertyName: 'seen' | 'junk' | 'flagged',
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

	return {
		// Handlers
		handleSetSeen,
		handleSyncUnseen,
		setFlaggedByThreadIDs,
		handleMoveThreads,
		handleSetSpamStatus,
		handleAddThreadsToMailbox,
		handleRemoveThreadsFromMailbox,
		junkOrDeleteThreads,
		// Resource exposed to the template (MailThread @set-flagged)
		setFlagged,
		// Toolbar option lists
		moveToOptions,
		addToOptions,
		removeFromOptions,
		showAddTo,
		showRemoveFrom,
		// Junk/Delete confirmation dialog
		showJunkOrDeleteThreads,
		junkOrDeleteThreadsOptions,
	}
}
