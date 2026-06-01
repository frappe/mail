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
const rootFrame = ref()
let mounted = false

function go(loggedIn: boolean) {
	$navigateTo(loggedIn ? AppShell : LandingPage, {
		frame: rootFrame.value,
		clearHistory: true,
	})
}

function onFrameLoaded() {
	if (mounted) return
	mounted = true
	go(session.isLoggedIn)
}

watch(
	() => session.isLoggedIn,
	(loggedIn) => {
		if (mounted) go(loggedIn)
	},
)
</script>
