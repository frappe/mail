import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import { userStore } from '@/stores/user'

import type { Identity } from '@/types'

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

	return { setUndoAction, undo }
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
	const { identities, blockedAddresses } = userStore()

	// Senders worth offering to block: drop the user's own identities and addresses already blocked,
	// and de-duplicate by email (keeping the first occurrence's display name).
	const blockableSenders = (senders: { name?: string; email?: string }[]) => {
		const own = new Set((identities.data ?? []).map((i: Identity) => i.email))
		const blocked = new Set<string>(blockedAddresses.data ?? [])
		const seen = new Set<string>()
		const result: BlockableSender[] = []
		for (const { name, email } of senders) {
			if (!email || own.has(email) || blocked.has(email) || seen.has(email)) continue
			seen.add(email)
			result.push({ name, email })
		}
		return result
	}

	const promptBlockSenders = (senders: { name?: string; email?: string }[]) => {
		const list = blockableSenders(senders)
		if (!list.length) return
		sendersToBlock.value = list
		showBlockSender.value = true
	}

	return { showBlockSender, sendersToBlock, promptBlockSenders }
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
