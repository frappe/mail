import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

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

export type Theme = 'light' | 'dark' | 'system'

const currentTheme = ref<Theme>('light')

export const useTheme = () => {
	const getSystemTheme = (): 'light' | 'dark' =>
		window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'

	const setTheme = (theme: Theme) => {
		currentTheme.value = theme
		document.documentElement.setAttribute(
			'data-theme',
			theme === 'system' ? getSystemTheme() : theme,
		)
	}

	const activeTheme = computed<'light' | 'dark'>(() =>
		currentTheme.value === 'system' ? getSystemTheme() : currentTheme.value,
	)

	return { currentTheme, getSystemTheme, setTheme, activeTheme }
}

export type GroupMessagesBy = 'none' | 'day' | 'month'

const showReadingPane = ref(false)
const groupMessagesBy = ref<GroupMessagesBy>('day')

export const useLayout = () => {
	const setShowReadingPane = (show: boolean) => {
		showReadingPane.value = show
	}

	const setGroupMessagesBy = (groupBy: GroupMessagesBy) => {
		groupMessagesBy.value = groupBy
	}

	return { showReadingPane, setShowReadingPane, groupMessagesBy, setGroupMessagesBy }
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
