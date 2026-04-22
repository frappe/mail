<template>
	<FrappeUIProvider>
		<Layout>
			<router-view />
		</Layout>
		<InstallPrompt v-if="isMobile" />
	</FrappeUIProvider>
</template>
<script setup lang="ts">
import { computed, onMounted, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider } from 'frappe-ui'

import { useScreenSize, useTheme } from '@/utils/composables'
import { showNotification } from '@/utils/push-notifications'
import DefaultLayout from '@/components/DefaultLayout.vue'
import InstallPrompt from '@/components/InstallPrompt.vue'
import LoginLayout from '@/components/LoginLayout.vue'

import type { NotificationPayload } from '@/types'

const { dataTheme } = useTheme()
const { isMobile } = useScreenSize()
const route = useRoute()

const Layout = computed(() => {
	if (route.meta.isLogin || route.meta.isSetup) return LoginLayout
	if (route.meta.noLayout) return 'div'
	return DefaultLayout
})

watchEffect(() => document.documentElement.setAttribute('data-theme', dataTheme.value))

onMounted(() =>
	window.frappePushNotification?.onMessage((payload: NotificationPayload) =>
		showNotification(payload),
	),
)
</script>
