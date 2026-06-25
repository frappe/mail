<template>
	<FrappeUIProvider>
		<Layout>
			<router-view />
		</Layout>
		<InstallPrompt v-if="isMobile" />
	</FrappeUIProvider>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider } from 'frappe-ui'

import { shouldIgnoreKeypress } from '@/utils'
import { useScreenSize, useTheme } from '@/utils/composables'
import { showNotification } from '@/utils/push-notifications'
import DefaultLayout from '@/components/DefaultLayout.vue'
import InstallPrompt from '@/components/InstallPrompt.vue'
import LoginLayout from '@/components/LoginLayout.vue'

import type { NotificationPayload } from '@/types'

const { dataTheme, cycleTheme } = useTheme()
const { isMobile } = useScreenSize()
const route = useRoute()

const Layout = computed(() => {
	if (route.meta.isLogin || route.meta.isSetup) return LoginLayout
	if (route.meta.noLayout) return 'div'
	return DefaultLayout
})

watchEffect(() => document.documentElement.setAttribute('data-theme', dataTheme.value))

// App-wide Cmd/Ctrl+Shift+L to cycle the color scheme (works on every page, not just the mailbox).
const handleThemeShortcut = (e: KeyboardEvent) => {
	if (
		(e.metaKey || e.ctrlKey) &&
		e.shiftKey &&
		e.key.toLowerCase() === 'l' &&
		!shouldIgnoreKeypress(e, true)
	) {
		e.preventDefault()
		cycleTheme()
	}
}

onMounted(() => {
	window.frappePushNotification?.onMessage((payload: NotificationPayload) =>
		showNotification(payload),
	)
	window.addEventListener('keydown', handleThemeShortcut)
})

onUnmounted(() => window.removeEventListener('keydown', handleThemeShortcut))
</script>
