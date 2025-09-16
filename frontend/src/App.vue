<template>
	<FrappeUIProvider>
		<Layout>
			<router-view />
		</Layout>
		<InstallPrompt v-if="isMobile" />
	</FrappeUIProvider>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider } from 'frappe-ui'

import { type Theme, useScreenSize, useTheme } from '@/utils/composables'
import { showNotification } from '@/utils/push-notifications'
import DefaultLayout from '@/components/DefaultLayout.vue'
import InstallPrompt from '@/components/InstallPrompt.vue'
import LoginLayout from '@/components/LoginLayout.vue'

import type { NotificationPayload } from '@/types'

const { isMobile } = useScreenSize()

const route = useRoute()

const Layout = computed(() => {
	if (route.meta.isLogin || route.meta.isSetup) return LoginLayout
	if (route.meta.noLayout) return 'div'
	return DefaultLayout
})

const { currentTheme, getSystemTheme, setTheme } = useTheme()

const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const handleSystemThemeChange = () => {
	if (currentTheme.value === 'system')
		document.documentElement.setAttribute('data-theme', getSystemTheme())
}

onMounted(() => {
	window.frappePushNotification?.onMessage((payload: NotificationPayload) =>
		showNotification(payload),
	)
	const storedTheme = localStorage.getItem('theme') as Theme | null
	setTheme(storedTheme || 'system')
	mediaQuery.addEventListener('change', handleSystemThemeChange)
})
onUnmounted(() => mediaQuery.removeEventListener('change', handleSystemThemeChange))
</script>
