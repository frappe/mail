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

import { useScreenSize } from '@/utils/composables'
import { showNotification } from '@/utils/push-notifications'
import { userStore } from '@/stores/user'
import DefaultLayout from '@/components/DefaultLayout.vue'
import InstallPrompt from '@/components/InstallPrompt.vue'
import LoginLayout from '@/components/LoginLayout.vue'

import type { NotificationPayload } from '@/types'

import { getDataTheme } from './utils'

const { userResource } = userStore()
const { isMobile } = useScreenSize()

const route = useRoute()

const Layout = computed(() => {
	if (route.meta.isLogin || route.meta.isSetup) return LoginLayout
	if (route.meta.noLayout) return 'div'
	return DefaultLayout
})

const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const setTheme = () =>
	document.documentElement.setAttribute(
		'data-theme',
		getDataTheme(userResource.data.color_scheme),
	)

onMounted(() => {
	window.frappePushNotification?.onMessage((payload: NotificationPayload) =>
		showNotification(payload),
	)
	if (!document.documentElement.getAttribute('data-theme')) setTheme()
	mediaQuery.addEventListener('change', setTheme)
})
onUnmounted(() => mediaQuery.removeEventListener('change', setTheme))
</script>
