import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { createResource } from 'frappe-ui'

import { raisePromiseToast, raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { COLOR_SCHEME, Identity, ScreenedAddress } from '@/types'

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
	const { setUndoAction, undo } = useUndo()

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
			account_id: store.accountId,
			emails,
			action: 'Reject',
		}),
		onSuccess: () => screenedAddresses.reload(),
	})

	const unscreenResource = createResource({
		url: 'mail.api.mail.unscreen_email_addresses',
		makeParams: ({ emails }: { emails: string[] }) => ({
			account_id: store.accountId,
			emails,
		}),
		onSuccess: () => screenedAddresses.reload(),
	})

	// Block the senders chosen in the prompt ('Ask to Block Sender' confirm). Blocking becomes the new
	// undo action: Cmd+Z unblocks (it does not also reverse the junk move, which stays).
	const blockSenders = (senders: BlockableSender[]) => {
		const emails = senders.map((sender) => sender.email)
		if (!emails.length) return

		setUndoAction(() => {
			const undoAction = () => unscreenResource.submit({ emails })
			const restored =
				emails.length === 1 ? __('Sender unblocked.') : __('Senders unblocked.')
			raisePromiseToast(undoAction, __('Undoing...'), restored)
		})

		const action = () => blockResource.submit({ emails })
		const success = emails.length === 1 ? __('Sender blocked.') : __('Senders blocked.')
		raisePromiseToast(action, __('Blocking...'), success, undo)
	}

	// Whether marking these senders as junk will auto-file their future mail into Junk (vs prompting
	// to block, or doing nothing when there's nothing blockable). Lets the caller show one accurate toast.
	const willJunkSenders = (senders: { name?: string; email?: string }[]) =>
		blockableSenders(senders).length > 0 &&
		activeAccount.value?.on_mark_as_junk !== 'Ask to Block Sender'

	// Open the block prompt for the senders of a just-junked message, in 'Ask to Block Sender' mode. The
	// default 'Junk Sender's Mail' screening now rides on the junk API call, so it's not handled here.
	const promptBlockSenders = (senders: { name?: string; email?: string }[]) => {
		if (activeAccount.value?.on_mark_as_junk !== 'Ask to Block Sender') return

		const list = blockableSenders(senders)
		if (!list.length) return

		sendersToBlock.value = list
		showBlockSender.value = true
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

const COLOR_SCHEME_CYCLE = ['System Default', 'Light Mode', 'Dark Mode'] as const

export const useTheme = () => {
	const { userResource } = userStore()

	const dataTheme = computed(() => {
		const colorScheme = userResource.data?.color_scheme || 'System Default'
		if (colorScheme === 'System Default') return systemIsDark.value ? 'dark' : 'light'
		return colorScheme === 'Dark Mode' ? 'dark' : 'light'
	})

	const updateColorScheme = createResource({
		url: 'frappe.client.set_value',
		makeParams: (color_scheme: COLOR_SCHEME) => ({
			doctype: 'User Settings',
			name: userResource.data?.user_settings,
			fieldname: { color_scheme },
		}),
		onSuccess: (data: { color_scheme: COLOR_SCHEME }) => {
			raiseToast(__('Color scheme updated to {0}.', [data.color_scheme]))
			userResource.reload()
		},
	})

	// Cycle System Default → Light → Dark. Bound to Cmd/Ctrl+Shift+L app-wide (see App.vue).
	const cycleTheme = () => {
		const current = userResource.data?.color_scheme
		const idx = COLOR_SCHEME_CYCLE.indexOf(current as COLOR_SCHEME)
		const next = COLOR_SCHEME_CYCLE[(idx + 1) % COLOR_SCHEME_CYCLE.length]
		updateColorScheme.submit(next)
	}

	return { dataTheme, cycleTheme }
}
