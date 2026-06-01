<template>
	<Frame ref="rootFrame" @loaded="onFrameLoaded" />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { $navigateTo } from 'nativescript-vue'

import { sessionStore } from '@/stores/session'
import AppShell from '@/pages/AppShell.vue'
import LandingPage from '@/pages/LandingPage.vue'

const session = sessionStore()

// Template ref to the root Frame — navigating against this explicit frame avoids
// Frame.topmost(), which resolves to the wrong frame while a modal is dismissing
// (the cause of the post-login white screen / getExitTransition crash).
const rootFrame = ref()

let mounted = false

function go(loggedIn: boolean) {
	$navigateTo(loggedIn ? AppShell : LandingPage, {
		frame: rootFrame.value,
		clearHistory: true,
	})
}

// The Frame's `loaded` event guarantees the native frame exists, so the initial
// navigation can't fail with "Failed to resolve frame".
function onFrameLoaded() {
	if (mounted) return
	mounted = true
	go(session.isLoggedIn)
}

// React to login/logout once the frame is up. Defer to the next macrotask so any
// in-flight modal (the OAuth WebView) finishes tearing down before we navigate —
// navigating mid-dismissal leaves a blank frame.
watch(
	() => session.isLoggedIn,
	(loggedIn) => {
		if (mounted) setTimeout(() => go(loggedIn), 0)
	},
)
</script>
