import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { createResource } from 'frappe-ui'

import { raisePromiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { Identity, ScreenedAddress } from '@/types'

export const useScreenSize = () => {
	const size = reactive({ width: window.innerWidth, height: window.innerHeight })

	const isMobile = computed(() => size.width < 640)

	const onResize = () => {
		size.width = window.innerWidth
		size.height = window.innerHeight
	}

	onMounted(() => window.addEventListener('resize', onResize))

	onUnmounted(() => window.removeEventListener('resize', onResize))

	return { size, isMobile }
}

const isSidebarOpen = ref(false)

export const useSidebar = () => {
	const openSidebar = () => (isSidebarOpen.value = true)
	const closeSidebar = () => (isSidebarOpen.value = false)

	return { isSidebarOpen, openSidebar, closeSidebar }
}

export const useTextEditorButtons = () => {
	const { isMobile } = useScreenSize()

	const alignButtons = ['Separator', 'Align Left', 'Align Center', 'Align Right']

	const buttons = computed(() => [
		'Paragraph',
		['Heading 2', 'Heading 3', 'Heading 4', 'Heading 5', 'Heading 6'],
		'Separator',
		'Bold',
		'Italic',
		'FontColor',
		...(isMobile.value ? [] : alignButtons),
		'Separator',
		'Bullet List',
		'Numbered List',
		'Separator',
		'Image',
		'Link',
	])

	return { buttons }
}

export const useVisualViewport = (calc: (viewport: VisualViewport) => string) => {
	const value = ref('0px')

	const update = () => {
		if (window.visualViewport) value.value = calc(window.visualViewport)
	}

	onMounted(() => {
		if (!window.visualViewport) return
		window.visualViewport.addEventListener('resize', update)
		window.visualViewport.addEventListener('scroll', update)

		update()

		onUnmounted(() => {
			if (!window.visualViewport) return
			window.visualViewport.removeEventListener('resize', update)
			window.visualViewport.removeEventListener('scroll', update)
		})
	})

	return value
}

const undoAction = ref<() => void>()

export const useUndo = () => {
	const setUndoAction = (action?: () => void) => (undoAction.value = action)

	const undo = () => {
		if (!undoAction.value) return
		undoAction.value()
		undoAction.value = undefined
	}

	// Wrap the current undo so `step` runs first — lets a side effect (e.g. a junk-list entry) be
	// reverted on top of the primary undo without replacing it.
	const prependUndoAction = (step: () => void) => {
		const prev = undoAction.value
		undoAction.value = () => {
			step()
			prev?.()
		}
	}

	return { setUndoAction, undo, prependUndoAction }
}

// Shared state for the "Block sender?" prompt shown after marking/moving mail to Junk. A single
// <BlockSenderModal> (rendered in MailboxView) reacts to this, so any view can open it.
export interface BlockableSender {
	name?: string
	email: string
}

const showBlockSender = ref(false)
const sendersToBlock = ref<BlockableSender[]>([])

export const useBlockSender = () => {
	const store = userStore()
	const { userResource, identities, screenedAddresses } = store
	const { setUndoAction, undo, prependUndoAction } = useUndo()

	// Read account/accountId off the store at call time — destructuring would snapshot the unwrapped
	// values and miss account switches while a component stays mounted.
	const activeAccount = computed(() =>
		userResource.data?.accounts?.find((a) => a.id === store.accountId),
	)

	// Senders worth offering to block: drop the user's own identities and addresses already blocked
	// (screened as Reject), and de-duplicate by email (keeping the first occurrence's display name).
	const blockableSenders = (senders: { name?: string; email?: string }[]) => {
		const own = new Set((identities.data ?? []).map((i: Identity) => i.email))
		const blocked = new Set<string>(
			(screenedAddresses.data ?? [])
				.filter((a: ScreenedAddress) => a.action === 'Reject')
				.map((a: ScreenedAddress) => a.email),
		)
		const seen = new Set<string>()
		const result: BlockableSender[] = []
		for (const { name, email } of senders) {
			if (!email || own.has(email) || blocked.has(email) || seen.has(email)) continue
			seen.add(email)
			result.push({ name, email })
		}
		return result
	}

	const blockResource = createResource({
		url: 'mail.api.mail.screen_email_addresses',
		makeParams: ({ emails }: { emails: string[] }) => ({
			account: store.account,
			emails,
			action: 'Reject',
		}),
		onSuccess: () => screenedAddresses.reload(),
	})

	const junkResource = createResource({
		url: 'mail.api.mail.screen_email_addresses',
		makeParams: ({ emails }: { emails: string[] }) => ({
			account: store.account,
			emails,
			action: 'Spam',
		}),
		onSuccess: () => screenedAddresses.reload(),
	})

	const unjunkResource = createResource({
		url: 'mail.api.mail.unscreen_email_addresses',
		makeParams: ({ emails }: { emails: string[] }) => ({ account: store.account, emails }),
		onSuccess: () => screenedAddresses.reload(),
	})

	const unblockResource = createResource({
		url: 'mail.api.mail.unscreen_email_addresses',
		makeParams: ({ emails }: { emails: string[] }) => ({ account: store.account, emails }),
		onSuccess: () => screenedAddresses.reload(),
	})

	// Block the senders chosen in the prompt ('Ask to Block Sender' confirm). Blocking becomes the new
	// undo action: Cmd+Z unblocks (it does not also reverse the junk move, which stays).
	const blockSenders = (senders: BlockableSender[]) => {
		const emails = senders.map((sender) => sender.email)
		if (!emails.length) return

		setUndoAction(() => {
			const undoAction = () => unblockResource.submit({ emails })
			const restored =
				emails.length === 1 ? __('Sender unblocked.') : __('Senders unblocked.')
			raisePromiseToast(undoAction, __('Undoing...'), restored)
		})

		const action = () => blockResource.submit({ emails })
		const success = emails.length === 1 ? __('Sender blocked.') : __('Senders blocked.')
		raisePromiseToast(action, __('Blocking...'), success, undo)
	}

	// File the senders' future mail into Junk (the default 'Junk Sender's Mail'). Side effect only — the
	// caller renders the toast (see willJunkSenders) so the junk action shows a single toast, not two.
	// Undoing the junk move also drops them from the junk list (composed onto that move's undo).
	const junkSenders = (senders: BlockableSender[]) => {
		const emails = senders.map((sender) => sender.email)
		if (!emails.length) return

		junkResource.submit({ emails })
		prependUndoAction(() => unjunkResource.submit({ emails }))
	}

	// Whether marking these senders as junk will auto-file their future mail into Junk (vs prompting
	// to block, or doing nothing when there's nothing blockable). Lets the caller show one accurate toast.
	const willJunkSenders = (senders: { name?: string; email?: string }[]) =>
		blockableSenders(senders).length > 0 &&
		activeAccount.value?.on_mark_as_junk !== 'Ask to Block Sender'

	// Apply the account's 'on mark as junk' behaviour to the senders of a just-junked message:
	// 'Ask to Block Sender' opens the prompt; otherwise silently junk their future mail.
	const promptBlockSenders = (senders: { name?: string; email?: string }[]) => {
		const list = blockableSenders(senders)
		if (!list.length) return

		if (activeAccount.value?.on_mark_as_junk === 'Ask to Block Sender') {
			sendersToBlock.value = list
			showBlockSender.value = true
			return
		}
		junkSenders(list)
	}

	return { showBlockSender, sendersToBlock, willJunkSenders, promptBlockSenders, blockSenders }
}

// Shared state for the Settings dialog, so any view can open it (optionally on a specific tab).
// <SettingsModal> (rendered in AppSidebar) reacts to `showSettings`, and selects `settingsTab` by
// label when it opens.
const showSettings = ref(false)
const settingsTab = ref('')

export const useSettings = () => {
	const openSettings = (tab = '') => {
		settingsTab.value = tab
		showSettings.value = true
	}

	return { showSettings, settingsTab, openSettings }
}

const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const systemIsDark = ref(mediaQuery.matches)
mediaQuery.addEventListener('change', () => (systemIsDark.value = mediaQuery.matches))

export const useTheme = () => {
	const { userResource } = userStore()

	const dataTheme = computed(() => {
		const colorScheme = userResource.data?.color_scheme || 'System Default'
		if (colorScheme === 'System Default') return systemIsDark.value ? 'dark' : 'light'
		return colorScheme === 'Dark Mode' ? 'dark' : 'light'
	})

	return { dataTheme }
}
