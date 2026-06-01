<template>
	<Frame ref="rootFrame" @loaded="onFrameLoaded" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { $navigateTo } from 'nativescript-vue'

import { sessionStore } from '@/stores/session'
import AppShell from '@/pages/AppShell.vue'
import LandingPage from '@/pages/LandingPage.vue'

const session = sessionStore()

// Template ref to the root Frame — navigating against this explicit frame is
// only needed for the initial route. Login/logout transitions are driven
// explicitly from the page handlers (see LandingPage / AppShell), which
// navigate their own frame at a settled point in the flow. Driving navigation
// from a reactive watch during the async OAuth flow was the cause of the
// post-login white screen.
const rootFrame = ref()
let mounted = false

function onFrameLoaded() {
	if (mounted) return
	mounted = true
	$navigateTo(session.isLoggedIn ? AppShell : LandingPage, {
		frame: rootFrame.value,
		clearHistory: true,
	})
}
</script>
